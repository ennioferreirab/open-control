"""Anthropic OAuth Provider — direct httpx + SSE, no LiteLLM."""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator

import httpx
from loguru import logger

from nanobot.providers.anthropic_oauth import get_anthropic_token
from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_BETA = "oauth-2025-04-20,prompt-caching-2024-07-31"

_REASONING_BUDGET_TOKENS: dict[str, int] = {
    "low": 1024,
    "medium": 8000,
    "max": 16000,
}


class AnthropicOAuthProvider(LLMProvider):
    """Anthropic provider using OAuth tokens (Claude Pro/Max subscription)."""

    def __init__(self, default_model: str = "anthropic-oauth/claude-sonnet-4-20250514"):
        super().__init__(api_key=None, api_base=None)
        self.default_model = default_model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_level: str | None = None,
    ) -> LLMResponse:
        model = _strip_prefix(model or self.default_model)
        token = get_anthropic_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "anthropic-version": ANTHROPIC_VERSION,
            "anthropic-beta": ANTHROPIC_BETA,
            "content-type": "application/json",
        }

        system_text, api_messages = _convert_messages(
            self._sanitize_empty_content(messages)
        )

        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
            "stream": True,
            "messages": api_messages,
        }
        if system_text:
            body["system"] = [
                {"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}
            ]
        if tools:
            body["tools"] = _convert_tools(tools)
            body["tool_choice"] = {"type": "auto"}

        if reasoning_level:
            budget = _REASONING_BUDGET_TOKENS.get(reasoning_level)
            if budget:
                body["thinking"] = {"type": "enabled", "budget_tokens": budget}
                body["temperature"] = 1.0  # Anthropic requires temp=1.0 with thinking

        try:
            content, tool_calls, finish_reason, usage, reasoning_content = await _request_anthropic(
                headers, body
            )
            return LLMResponse(
                content=content or None,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage,
                reasoning_content=reasoning_content,
            )
        except Exception as e:
            logger.error(f"Anthropic OAuth error: {e}")
            return LLMResponse(content=f"Error calling Anthropic: {e}", finish_reason="error")

    def get_default_model(self) -> str:
        return self.default_model

    def list_models(self) -> list[str]:
        """Query Anthropic API for available models on this OAuth subscription."""
        from nanobot.providers.anthropic_oauth import get_anthropic_token

        try:
            token = get_anthropic_token()
            resp = httpx.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "Authorization": f"Bearer {token}",
                    "anthropic-version": ANTHROPIC_VERSION,
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            return [
                f"anthropic-oauth/{m['id']}"
                for m in resp.json().get("data", [])
            ]
        except Exception:
            return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_prefix(model: str) -> str:
    for prefix in ("anthropic-oauth/", "anthropic_oauth/"):
        if model.startswith(prefix):
            return model.split("/", 1)[1]
    return model


def _convert_messages(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Convert OpenAI-style messages to Anthropic Messages API format."""
    system_text = ""
    api_messages: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if role == "system":
            system_text = content if isinstance(content, str) else ""
            continue

        if role == "user":
            api_messages.append({"role": "user", "content": _convert_content(content)})
            continue

        if role == "assistant":
            blocks: list[dict[str, Any]] = []
            if isinstance(content, str) and content:
                blocks.append({"type": "text", "text": content})
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                        blocks.append({"type": "text", "text": item["text"]})

            for tc in msg.get("tool_calls", []) or []:
                fn = tc.get("function") or {}
                args = fn.get("arguments", "{}")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", "tool_0"),
                    "name": fn.get("name", ""),
                    "input": args,
                })

            if blocks:
                api_messages.append({"role": "assistant", "content": blocks})
            continue

        if role == "tool":
            tool_content = content if isinstance(content, str) else json.dumps(content or "")
            api_messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", "tool_0"),
                    "content": tool_content,
                }],
            })
            continue

    return system_text, api_messages


def _convert_content(content: Any) -> str | list[dict[str, Any]]:
    """Convert user message content to Anthropic format."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        blocks: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                blocks.append({"type": "text", "text": item.get("text", "")})
            elif item.get("type") == "image_url":
                url = (item.get("image_url") or {}).get("url", "")
                if url.startswith("data:"):
                    # data:image/png;base64,... format
                    meta, data = url.split(",", 1) if "," in url else ("", url)
                    media_type = meta.split(";")[0].split(":")[1] if ":" in meta else "image/png"
                    blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": data,
                        },
                    })
                else:
                    blocks.append({
                        "type": "image",
                        "source": {"type": "url", "url": url},
                    })
        return blocks or content
    return str(content) if content else "(empty)"


def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI function-calling tools to Anthropic format."""
    converted: list[dict[str, Any]] = []
    for tool in tools:
        fn = (tool.get("function") or {}) if tool.get("type") == "function" else tool
        name = fn.get("name")
        if not name:
            continue
        converted.append({
            "name": name,
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
        })
    return converted


# ---------------------------------------------------------------------------
# SSE streaming
# ---------------------------------------------------------------------------

async def _request_anthropic(
    headers: dict[str, str],
    body: dict[str, Any],
) -> tuple[str, list[ToolCallRequest], str, dict[str, int], str | None]:
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", ANTHROPIC_API_URL, headers=headers, json=body) as resp:
            if resp.status_code != 200:
                text = await resp.aread()
                raise RuntimeError(f"HTTP {resp.status_code}: {text.decode('utf-8', 'ignore')}")
            return await _consume_sse(resp)


async def _iter_sse(response: httpx.Response) -> AsyncGenerator[dict[str, Any], None]:
    """Iterate over Server-Sent Events."""
    buffer: list[str] = []
    async for line in response.aiter_lines():
        if line == "":
            if buffer:
                data_lines = [ln[5:].strip() for ln in buffer if ln.startswith("data:")]
                buffer = []
                if not data_lines:
                    continue
                data = "\n".join(data_lines).strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue
            continue
        buffer.append(line)


async def _consume_sse(
    response: httpx.Response,
) -> tuple[str, list[ToolCallRequest], str, dict[str, int], str | None]:
    """Parse Anthropic SSE stream into content + tool calls + reasoning."""
    content = ""
    thinking_text = ""
    tool_calls: list[ToolCallRequest] = []
    tool_buffers: dict[int, dict[str, Any]] = {}
    thinking_blocks: set[int] = set()
    finish_reason = "stop"
    usage: dict[str, int] = {}

    async for event in _iter_sse(response):
        event_type = event.get("type")

        if event_type == "content_block_start":
            idx = event.get("index", 0)
            block = event.get("content_block") or {}
            if block.get("type") == "tool_use":
                tool_buffers[idx] = {
                    "id": block.get("id", f"tool_{idx}"),
                    "name": block.get("name", ""),
                    "arguments_json": "",
                }
            elif block.get("type") == "thinking":
                thinking_blocks.add(idx)

        elif event_type == "content_block_delta":
            idx = event.get("index", 0)
            delta = event.get("delta") or {}
            delta_type = delta.get("type")

            if delta_type == "text_delta":
                content += delta.get("text", "")
            elif delta_type == "input_json_delta":
                if idx in tool_buffers:
                    tool_buffers[idx]["arguments_json"] += delta.get("partial_json", "")
            elif delta_type == "thinking_delta":
                if idx in thinking_blocks:
                    thinking_text += delta.get("thinking", "")

        elif event_type == "content_block_stop":
            idx = event.get("index", 0)
            thinking_blocks.discard(idx)
            if idx in tool_buffers:
                buf = tool_buffers.pop(idx)
                raw = buf["arguments_json"]
                try:
                    args = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    args = {"raw": raw}
                tool_calls.append(ToolCallRequest(
                    id=buf["id"],
                    name=buf["name"],
                    arguments=args,
                ))

        elif event_type == "message_delta":
            delta = event.get("delta") or {}
            stop_reason = delta.get("stop_reason")
            if stop_reason:
                finish_reason = _map_stop_reason(stop_reason)
            u = event.get("usage") or {}
            if u.get("output_tokens"):
                usage["completion_tokens"] = u["output_tokens"]

        elif event_type == "message_start":
            msg = event.get("message") or {}
            u = msg.get("usage") or {}
            if u.get("input_tokens"):
                usage["prompt_tokens"] = u["input_tokens"]

        elif event_type == "error":
            error = event.get("error") or {}
            raise RuntimeError(f"Anthropic stream error: {error.get('message', event)}")

    usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
    return content, tool_calls, finish_reason, usage, thinking_text or None


_STOP_REASON_MAP = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}


def _map_stop_reason(reason: str) -> str:
    return _STOP_REASON_MAP.get(reason, "stop")
