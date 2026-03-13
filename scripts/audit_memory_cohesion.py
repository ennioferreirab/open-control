from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from mc.audit.memory_cohesion import audit_memory_cohesion, render_report_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a live memory cohesion audit.")
    parser.add_argument("--root", type=Path, default=Path.home() / ".nanobot")
    parser.add_argument("--board-name", default="default")
    parser.add_argument("--nanobot-agent", default="nanobot")
    parser.add_argument("--cc-agent", default="offer-strategist")
    parser.add_argument("--nanobot-model", default="openai/gpt-4.1-mini")
    parser.add_argument("--cc-model", default="openai/gpt-4.1-mini")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--artifact-upload-path", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser


async def _main() -> int:
    args = build_parser().parse_args()
    report = await audit_memory_cohesion(
        root=args.root,
        nanobot_model=args.nanobot_model,
        cc_model=args.cc_model,
        board_name=args.board_name,
        nanobot_agent=args.nanobot_agent,
        cc_agent=args.cc_agent,
        base_url=args.base_url,
        artifact_upload_path=args.artifact_upload_path,
    )
    markdown = render_report_markdown(report)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
