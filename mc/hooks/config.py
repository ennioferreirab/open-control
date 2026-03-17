"""Hook factory configuration."""

from __future__ import annotations


from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HookConfig:
    plan_pattern: str = "docs/plans/*.md"
    tracker_dir: str = ".claude/plan-tracker"
    state_dir: str = ".claude/hook-state"


def get_config() -> HookConfig:
    return HookConfig()


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent
