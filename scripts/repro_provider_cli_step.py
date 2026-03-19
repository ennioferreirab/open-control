"""Reproduce a real provider-cli step launch against a live local MC stack.

This script resolves the exact step context from Convex, builds the provider-cli
command used by the runtime, launches the provider through the same
ProviderProcessSupervisor boundary, and prints the first streamed events.

Example:
    CONVEX_URL=http://127.0.0.1:3210 uv run python scripts/repro_provider_cli_step.py \
      --task-id m97dyj5gbteak0703b1aqpek2183139w \
      --step-id ks7csb35fv9jt1fwbp91dj60v5830bmr
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any

from mc.application.execution.context_builder import ContextBuilder
from mc.application.execution.post_processing import build_execution_engine
from mc.bridge import ConvexBridge
from mc.contexts.provider_cli.providers.claude_code import ClaudeCodeCLIParser
from mc.runtime.provider_cli.process_supervisor import ProviderProcessSupervisor


async def _load_request(task_id: str, step_id: str, bridge: ConvexBridge) -> tuple[Any, Any]:
    steps = bridge.get_steps_by_task(task_id)
    step = next((item for item in steps if item.get("id") == step_id), None)
    if step is None:
        raise SystemExit(f"Step {step_id!r} not found for task {task_id!r}")

    request = await ContextBuilder(bridge).build_step_context(task_id, step)
    strategy = build_execution_engine().get_strategy(request.runner_type.PROVIDER_CLI)
    return request, strategy


async def _run(args: argparse.Namespace) -> int:
    convex_url = args.convex_url or os.environ.get("CONVEX_URL")
    if not convex_url:
        raise SystemExit("Set --convex-url or CONVEX_URL")

    bridge = ConvexBridge(deployment_url=convex_url, admin_key=os.environ.get("CONVEX_ADMIN_KEY"))
    request, strategy = await _load_request(args.task_id, args.step_id, bridge)
    command = strategy._build_command(request)

    print(f"task_id={args.task_id}")
    print(f"step_id={args.step_id}")
    print(f"memory_workspace={request.memory_workspace}")
    print(f"cwd={strategy._cwd}")
    print(f"has_mcp_config={'--mcp-config' in command}")
    print(f"command_head={command[:12]}")

    supervisor = ProviderProcessSupervisor()
    parser = ClaudeCodeCLIParser(supervisor=supervisor)
    handle = await parser.start_session(
        mc_session_id=f"repro-{args.task_id}-{args.step_id}",
        command=command,
        cwd=strategy._cwd,
    )
    print(f"pid={handle.pid}")

    stream_iter = supervisor.stream_output(handle).__aiter__()
    try:
        for index in range(args.max_chunks):
            try:
                chunk = await asyncio.wait_for(anext(stream_iter), timeout=args.chunk_timeout)
            except StopAsyncIteration:
                print("stream_eof")
                break
            except TimeoutError:
                print(f"chunk_timeout={args.chunk_timeout}")
                break

            print(f"chunk[{index}] bytes={len(chunk)}")
            text = chunk.decode("utf-8", errors="replace")
            for raw_line in text.splitlines()[: args.raw_lines]:
                print(f"raw={raw_line[:400]}")
            for event in parser.parse_output(chunk)[: args.max_events_per_chunk]:
                event_payload = {
                    "kind": event.kind,
                    "text": (event.text or "")[:200],
                    "provider_session_id": event.provider_session_id,
                    "metadata": event.metadata,
                }
                print("event=" + json.dumps(event_payload, ensure_ascii=True))
    finally:
        await supervisor.kill(handle)
        await supervisor.wait_for_exit(handle)

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--step-id", required=True)
    parser.add_argument("--convex-url")
    parser.add_argument("--chunk-timeout", type=float, default=15.0)
    parser.add_argument("--max-chunks", type=int, default=3)
    parser.add_argument("--raw-lines", type=int, default=2)
    parser.add_argument("--max-events-per-chunk", type=int, default=5)
    return parser


def main() -> int:
    return asyncio.run(_run(_build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
