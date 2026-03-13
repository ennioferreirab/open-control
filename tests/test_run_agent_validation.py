from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_agent_validation.py"


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


def test_parse_args_defaults_to_isolated_workspace_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_agent_validation.py",
            "offer-strategist",
        ],
    )

    args = module.parse_args()

    assert args.workspace_mode == "isolated"


def test_parse_args_accepts_audit_workspace_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_agent_validation.py",
            "offer-strategist",
            "--workspace-mode",
            "audit",
        ],
    )

    args = module.parse_args()

    assert args.workspace_mode == "audit"


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


def test_validation_workspace_isolated_sets_temp_home(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    monkeypatch.setenv("HOME", "/tmp/original-home")

    with module.validation_workspace("isolated") as meta:
        assert meta["workspace_mode"] == "isolated"
        assert meta["workspace_scope"] == "isolated"
        assert Path(os.environ["HOME"]) == meta["home"]

    assert os.environ["HOME"] == "/tmp/original-home"


@pytest.mark.asyncio
async def test_execute_run_uses_runtime_engine_factory(tmp_path: Path) -> None:
    module = load_module()
    module.bootstrap_runtime = lambda: None
    module.build_request = lambda *args, **kwargs: SimpleNamespace(task_id="validation-task")
    fake_engine = SimpleNamespace(
        run=AsyncMock(return_value=SimpleNamespace(success=True, output="ok", error_message=None))
    )

    agent = module.LoadedAgent(
        agent_name="offer-strategist",
        config_path=Path("/tmp/offer-strategist/config.yaml"),
        data=SimpleNamespace(name="offer-strategist", model="gpt-5.4"),
        runner=SimpleNamespace(value="nanobot"),
    )
    scenario = module.LoadedScenario(
        agent_name="offer-strategist",
        scenario_path=Path("/tmp/offer-strategist.md"),
        prompt="Scenario prompt",
    )

    module.build_execution_engine = MagicMock(return_value=fake_engine)
    module.write_result = lambda run: None

    run = await module.execute_run(
        agent,
        scenario,
        "20260312",
        tmp_path,
        reasoning_level=None,
        workspace_mode="isolated",
    )

    module.build_execution_engine.assert_called_once_with()
    assert run.production_hooks is True
    assert run.workspace_mode == "isolated"


def test_write_result_includes_validation_mode_metadata(tmp_path: Path) -> None:
    module = load_module()
    result_path = tmp_path / "result.md"
    run = module.ScenarioRun(
        agent_name="offer-strategist",
        runner="nanobot",
        model="gpt-5.4",
        reasoning_level="medium",
        workspace_mode="audit",
        production_hooks=True,
        workspace_scope="real",
        history_interpretation="Audit mode uses the real workspace.",
        success=True,
        duration_seconds=1.23,
        prompt="Prompt",
        output="Output",
        scenario_path=Path("/tmp/scenario.md"),
        result_path=result_path,
    )

    module.write_result(run)
    content = result_path.read_text(encoding="utf-8")

    assert "`workspace_mode`: audit" in content
    assert "`production_hooks`: yes" in content
    assert "## Validation Mode" in content
