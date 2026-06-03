"""ACP utility turn — one-shot prompts through the claude-code harness with no tools.

Run one prompt through the claude-code ACP harness with no tools; return assistant text.
A completion-equivalent over ACP for internal utility calls (routing, memory).
"""

from __future__ import annotations

import asyncio
import json
import logging

from mc.infrastructure.acp.harness_registry import get_harness, resolve_model
from mc.infrastructure.providers.errors import ProviderError
from mc.infrastructure.runtime_home import get_workspace_dir

logger = logging.getLogger(__name__)


async def run_utility_turn(
    prompt: str,
    *,
    tier: str = "low",
    timeout_s: float = 180.0,
    cwd: str | None = None,
) -> str:
    """Run one prompt through the claude-code ACP harness with no tools; return assistant text.

    A completion-equivalent over ACP for internal utility calls (routing, memory).

    Args:
        prompt: The full prompt text to send.
        tier: Model tier label ("low", "medium", "high"). Defaults to "low".
        timeout_s: Maximum seconds to wait for the turn to complete.
        cwd: Working directory for the harness subprocess. Defaults to workspace dir.

    Returns:
        Stripped assistant response text.

    Raises:
        ProviderError: On timeout, subprocess failure, or empty response.
    """
    from mc.infrastructure.acp.client import AcpClient

    spec = get_harness("claude-code")
    model = resolve_model(spec, tier)
    work_dir = cwd or str(get_workspace_dir())

    import pathlib

    pathlib.Path(work_dir).mkdir(parents=True, exist_ok=True)

    try:
        async with AcpClient(
            list(spec.launch_command),
            cwd=work_dir,
            model=model,
            mcp_servers=None,
            allowed_tools=[],
        ) as client:
            try:
                result = await asyncio.wait_for(client.prompt(prompt), timeout=timeout_s)
            except TimeoutError as exc:
                raise ProviderError(f"ACP utility turn timed out after {timeout_s}s") from exc
    except ProviderError:
        raise
    except Exception as exc:
        raise ProviderError(f"ACP utility turn failed: {exc}") from exc

    text = (result.text or "").strip()
    if not text:
        raise ProviderError("ACP utility turn returned empty text")
    return text


def extract_json(text: str) -> dict:
    """Parse the first balanced JSON object from *text*.

    Strips markdown code fences, then scans for the first ``{`` and
    walks matching braces to extract the JSON block. Tolerates agent
    preamble before the object.

    Raises:
        ProviderError: If no parseable JSON object is found.
    """
    # Strip markdown fences
    lines = text.splitlines()
    stripped_lines = [ln for ln in lines if not ln.strip().startswith("```")]
    cleaned = "\n".join(stripped_lines)

    start = cleaned.find("{")
    if start == -1:
        raise ProviderError(f"no parseable JSON in utility turn output: {text[:300]}")

    depth = 0
    for i, ch in enumerate(cleaned[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    break

    raise ProviderError(f"no parseable JSON in utility turn output: {text[:300]}")
