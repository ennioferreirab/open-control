from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_agent_validation.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("run_agent_validation", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_args_accepts_reasoning_level(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_agent_validation.py",
            "offer-strategist",
            "--reasoning-level",
            "medium",
        ],
    )

    args = module.parse_args()

    assert args.reasoning_level == "medium"


def test_build_request_sets_reasoning_level() -> None:
    module = load_module()
    module.bootstrap_runtime = lambda: None
    module.EntityType = SimpleNamespace(TASK="task")
    module.ExecutionRequest = lambda **kwargs: SimpleNamespace(**kwargs)
    module.RunnerType = SimpleNamespace(CLAUDE_CODE="claude-code", NANOBOT="nanobot")

    agent = module.LoadedAgent(
        agent_name="offer-strategist",
        config_path=Path("/tmp/offer-strategist/config.yaml"),
        data=SimpleNamespace(
            name="offer-strategist",
            prompt="Prompt",
            model="openai-codex/gpt-5.4",
            skills=["consulting-positioning"],
        ),
        runner="nanobot",
    )
    scenario = module.LoadedScenario(
        agent_name="offer-strategist",
        scenario_path=Path("/tmp/offer-strategist.md"),
        prompt="Scenario prompt",
    )

    request = module.build_request(agent, scenario, "20260308", reasoning_level="medium")

    assert request.reasoning_level == "medium"
