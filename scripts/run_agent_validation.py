#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import os
import re
import shutil
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from textwrap import indent
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_AGENTS = [
    "offer-strategist",
    "sales-revops",
    "contracts-risk",
    "delivery-systems",
    "marketing-copy",
    "finance-pricing",
]
REASONING_LEVELS = ("low", "medium", "max")
WORKSPACE_MODES = ("isolated", "audit")

AGENTS_ROOT = Path.home() / ".nanobot" / "agents"
SCENARIOS_ROOT = Path.home() / ".nanobot" / "private" / "knowledge-validation"
RESULTS_ROOT = SCENARIOS_ROOT / "results"
REAL_HOME = Path.home()
INPUT_BLOCK_PATTERN = re.compile(
    r"## Input de Teste\s*```(?:text)?\n(.*?)```",
    re.DOTALL,
)

ExecutionEngine = None
build_execution_engine = None
EntityType = None
ExecutionRequest = None
RunnerType = None
validate_agent_file = None
is_cc_model = None


class ValidationError(RuntimeError):
    """Expected validation/setup failure for one scenario run."""


@dataclass
class ScenarioRun:
    agent_name: str
    runner: str
    model: str
    reasoning_level: str | None
    workspace_mode: str
    production_hooks: bool
    workspace_scope: str
    history_interpretation: str
    success: bool
    duration_seconds: float
    prompt: str
    output: str
    scenario_path: Path
    result_path: Path
    error_message: str | None = None


@dataclass
class LoadedScenario:
    agent_name: str
    scenario_path: Path
    prompt: str


@dataclass
class LoadedAgent:
    agent_name: str
    config_path: Path
    data: Any
    runner: Any


def bootstrap_runtime() -> None:
    global ExecutionEngine, build_execution_engine, EntityType, ExecutionRequest, RunnerType
    global validate_agent_file, is_cc_model

    if ExecutionEngine is not None:
        return

    try:
        from mc.application.execution.engine import ExecutionEngine as _ExecutionEngine
        from mc.application.execution.post_processing import (
            build_execution_engine as _build_execution_engine,
        )
        from mc.application.execution.request import (
            EntityType as _EntityType,
        )
        from mc.application.execution.request import (
            ExecutionRequest as _ExecutionRequest,
        )
        from mc.application.execution.request import (
            RunnerType as _RunnerType,
        )
        from mc.infrastructure.agents.yaml_validator import (
            validate_agent_file as _validate_agent_file,
        )
        from mc.types import is_cc_model as _is_cc_model
    except ModuleNotFoundError as exc:
        if exc.name in {"convex", "nanobot", "claude_code"}:
            venv_python = REPO_ROOT / ".venv" / "bin" / "python"
            raise SystemExit(
                "Missing runtime dependency '\n"
                f"{exc.name}' while importing Mission Control. Run this harness with "
                f"the project virtualenv instead:\n\n  {venv_python} {Path(__file__).resolve()} --all\n"
            ) from exc
        raise

    ExecutionEngine = _ExecutionEngine
    build_execution_engine = _build_execution_engine
    EntityType = _EntityType
    ExecutionRequest = _ExecutionRequest
    RunnerType = _RunnerType
    validate_agent_file = _validate_agent_file
    is_cc_model = _is_cc_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Mission Control validation scenarios against real local agents.",
    )
    parser.add_argument("agents", nargs="*", help="Agent names to run")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run the default consulting-agent validation set.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load configs and scenarios without executing providers.",
    )
    parser.add_argument(
        "--reasoning-level",
        choices=REASONING_LEVELS,
        default=None,
        help="Override reasoning level for the benchmark run.",
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=RESULTS_ROOT,
        help="Override the validation results root directory.",
    )
    parser.add_argument(
        "--workspace-mode",
        choices=WORKSPACE_MODES,
        default="isolated",
        help="Use isolated temporary workspaces (default) or audit against the real ~/.nanobot workspace.",
    )
    args = parser.parse_args()
    if args.all and args.agents:
        parser.error("Use either positional agent names or --all, not both.")
    if not args.all and not args.agents:
        parser.error("Pass one or more agent names, or use --all.")
    return args


def resolve_agent_names(args: argparse.Namespace) -> list[str]:
    if args.all:
        return list(DEFAULT_AGENTS)
    seen: set[str] = set()
    ordered: list[str] = []
    for name in args.agents:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def load_scenario(agent_name: str) -> LoadedScenario:
    scenario_path = SCENARIOS_ROOT / f"{agent_name}.md"
    if not scenario_path.is_file():
        raise ValidationError(f"Scenario file not found: {scenario_path}")
    content = scenario_path.read_text(encoding="utf-8")
    match = INPUT_BLOCK_PATTERN.search(content)
    if not match:
        raise ValidationError(
            f"Scenario file is missing an 'Input de Teste' block: {scenario_path}"
        )
    prompt = match.group(1).strip()
    if not prompt:
        raise ValidationError(f"Scenario input block is empty: {scenario_path}")
    return LoadedScenario(agent_name=agent_name, scenario_path=scenario_path, prompt=prompt)


def load_agent(agent_name: str) -> LoadedAgent:
    bootstrap_runtime()
    config_path = AGENTS_ROOT / agent_name / "config.yaml"
    if not config_path.is_file():
        raise ValidationError(f"Agent config not found: {config_path}")
    result = validate_agent_file(config_path)
    if isinstance(result, list):
        joined = "\n".join(f"- {item}" for item in result)
        raise ValidationError(f"Invalid agent config for {agent_name}:\n{joined}")
    runner = determine_runner(result)
    return LoadedAgent(
        agent_name=agent_name,
        config_path=config_path,
        data=result,
        runner=runner,
    )


def determine_runner(agent: Any) -> Any:
    bootstrap_runtime()
    model = agent.model or ""
    backend = (agent.backend or "").strip()
    if backend == RunnerType.CLAUDE_CODE.value or is_cc_model(model):
        return RunnerType.CLAUDE_CODE
    return RunnerType.NANOBOT


def build_request(
    agent: LoadedAgent,
    scenario: LoadedScenario,
    run_stamp: str,
    reasoning_level: str | None = None,
) -> Any:
    bootstrap_runtime()
    task_id = f"validation-{agent.agent_name}-{run_stamp}"
    return ExecutionRequest(
        entity_type=EntityType.TASK,
        entity_id=task_id,
        task_id=task_id,
        title=scenario.prompt,
        description=None,
        agent=agent.data,
        agent_name=agent.data.name,
        agent_prompt=agent.data.prompt,
        agent_model=agent.data.model,
        agent_skills=agent.data.skills,
        runner_type=agent.runner,
        reasoning_level=reasoning_level,
        is_cc=agent.runner == RunnerType.CLAUDE_CODE,
        model=agent.data.model,
    )


def make_run_dir(results_root: Path) -> tuple[str, Path]:
    run_stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = results_root / run_stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_stamp, run_dir


def describe_history_interpretation(workspace_mode: str) -> str:
    if workspace_mode == "audit":
        return "Audit mode uses the real workspace, so missing history is evaluated against the live agent state."
    return "Isolated mode uses a temporary workspace, so missing history reflects this validation run only."


@contextmanager
def validation_workspace(workspace_mode: str):
    if workspace_mode == "audit":
        yield {"workspace_mode": "audit", "workspace_scope": "real", "home": REAL_HOME}
        return

    with tempfile.TemporaryDirectory(prefix="nanobot-validation-") as tmp_dir:
        temp_home = Path(tmp_dir)
        previous_home = os.environ.get("HOME")
        os.environ["HOME"] = str(temp_home)

        source_runtime = REAL_HOME / ".nanobot"
        target_runtime = temp_home / ".nanobot"
        target_runtime.mkdir(parents=True, exist_ok=True)
        for filename in ("config.json", "anthropic_oauth.json", "memory_settings.json"):
            source = source_runtime / filename
            if source.exists():
                shutil.copy2(source, target_runtime / filename)

        try:
            yield {
                "workspace_mode": "isolated",
                "workspace_scope": "isolated",
                "home": temp_home,
            }
        finally:
            if previous_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = previous_home


def write_result(run: ScenarioRun) -> None:
    status = "success" if run.success else "failed"
    lines = [
        f"# Validation Result: `{run.agent_name}`",
        "",
        f"- `status`: {status}",
        f"- `runner`: {run.runner}",
        f"- `model`: {run.model}",
        f"- `reasoning_level`: {run.reasoning_level or '-'}",
        f"- `workspace_mode`: {run.workspace_mode}",
        f"- `workspace_scope`: {run.workspace_scope}",
        f"- `production_hooks`: {'yes' if run.production_hooks else 'no'}",
        f"- `duration_seconds`: {run.duration_seconds:.2f}",
        f"- `scenario`: {run.scenario_path}",
        "",
        "## Validation Mode",
        "",
        run.history_interpretation,
        "",
        "## Prompt",
        "",
        "```text",
        run.prompt,
        "```",
        "",
    ]
    if run.error_message:
        lines.extend(
            [
                "## Error",
                "",
                "```text",
                run.error_message,
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Output",
            "",
            "```text",
            run.output.strip() or "<empty output>",
            "```",
            "",
        ]
    )
    run.result_path.write_text("\n".join(lines), encoding="utf-8")


def write_index(run_dir: Path, runs: list[ScenarioRun]) -> Path:
    lines = [
        "# Agent Validation Run",
        "",
        f"- `run_dir`: {run_dir}",
        f"- `generated_at`: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "| Agent | Runner | Mode | Hooks | Model | Reasoning | Status | Duration (s) | Result |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | --- |",
    ]
    for run in runs:
        status = "success" if run.success else "failed"
        lines.append(
            f"| {run.agent_name} | {run.runner} | {run.workspace_mode} | {'prod' if run.production_hooks else 'custom'} | {run.model} | {run.reasoning_level or '-'} | {status} | {run.duration_seconds:.2f} | {run.result_path.name} |"
        )
    lines.append("")
    index_path = run_dir / "index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
    return index_path


async def execute_run(
    agent: LoadedAgent,
    scenario: LoadedScenario,
    run_stamp: str,
    run_dir: Path,
    reasoning_level: str | None,
    workspace_mode: str,
) -> ScenarioRun:
    bootstrap_runtime()
    request = build_request(agent, scenario, run_stamp, reasoning_level=reasoning_level)
    result_path = run_dir / f"{agent.agent_name}.md"
    started = time.perf_counter()
    with validation_workspace(workspace_mode) as mode_meta:
        engine = build_execution_engine()
        result = await engine.run(request)
    duration = time.perf_counter() - started
    error_message = result.error_message if not result.success else None
    output = result.output or ""
    if not result.success and not output:
        output = error_message or "<no output>"
    run = ScenarioRun(
        agent_name=agent.agent_name,
        runner=agent.runner.value,
        model=agent.data.model or "-",
        reasoning_level=reasoning_level,
        workspace_mode=mode_meta["workspace_mode"],
        production_hooks=True,
        workspace_scope=mode_meta["workspace_scope"],
        history_interpretation=describe_history_interpretation(mode_meta["workspace_mode"]),
        success=result.success,
        duration_seconds=duration,
        prompt=scenario.prompt,
        output=output,
        scenario_path=scenario.scenario_path,
        result_path=result_path,
        error_message=error_message,
    )
    write_result(run)
    return run


def make_failure_run(
    agent_name: str,
    runner: str,
    model: str,
    reasoning_level: str | None,
    workspace_mode: str,
    scenario_path: Path | None,
    prompt: str,
    error_message: str,
    result_path: Path,
) -> ScenarioRun:
    run = ScenarioRun(
        agent_name=agent_name,
        runner=runner,
        model=model,
        reasoning_level=reasoning_level,
        workspace_mode=workspace_mode,
        production_hooks=True,
        workspace_scope="real" if workspace_mode == "audit" else "isolated",
        history_interpretation=describe_history_interpretation(workspace_mode),
        success=False,
        duration_seconds=0.0,
        prompt=prompt,
        output=error_message,
        scenario_path=scenario_path or Path("<missing scenario>"),
        result_path=result_path,
        error_message=error_message,
    )
    write_result(run)
    return run


def print_dry_run(
    agent: LoadedAgent, scenario: LoadedScenario, reasoning_level: str | None
) -> None:
    print(f"agent={agent.agent_name}")
    print(f"runner={agent.runner.value}")
    print(f"model={agent.data.model or '-'}")
    print(f"reasoning_level={reasoning_level or '-'}")
    print(f"config={agent.config_path}")
    print(f"scenario={scenario.scenario_path}")
    print("prompt_preview=")
    print(indent(scenario.prompt[:800], prefix="  "))
    print()


async def main_async(args: argparse.Namespace) -> int:
    bootstrap_runtime()
    agent_names = resolve_agent_names(args)
    loaded: list[tuple[LoadedAgent, LoadedScenario]] = []

    for agent_name in agent_names:
        agent = load_agent(agent_name)
        scenario = load_scenario(agent_name)
        loaded.append((agent, scenario))

    if args.dry_run:
        for agent, scenario in loaded:
            print_dry_run(agent, scenario, args.reasoning_level)
        return 0

    run_stamp, run_dir = make_run_dir(args.results_root.expanduser())
    runs: list[ScenarioRun] = []

    for agent_name in agent_names:
        result_path = run_dir / f"{agent_name}.md"
        try:
            agent = load_agent(agent_name)
            scenario = load_scenario(agent_name)
            run = await execute_run(
                agent,
                scenario,
                run_stamp,
                run_dir,
                reasoning_level=args.reasoning_level,
                workspace_mode=args.workspace_mode,
            )
        except Exception as exc:
            scenario_path = None
            prompt = ""
            runner = "unknown"
            model = "-"
            try:
                scenario = load_scenario(agent_name)
                scenario_path = scenario.scenario_path
                prompt = scenario.prompt
            except Exception:
                pass
            try:
                agent = load_agent(agent_name)
                runner = agent.runner.value
                model = agent.data.model or "-"
            except Exception:
                pass
            run = make_failure_run(
                agent_name=agent_name,
                runner=runner,
                model=model,
                reasoning_level=args.reasoning_level,
                workspace_mode=args.workspace_mode,
                scenario_path=scenario_path,
                prompt=prompt,
                error_message=f"{type(exc).__name__}: {exc}",
                result_path=result_path,
            )
        runs.append(run)
        status = "OK" if run.success else "FAIL"
        print(f"[{status}] {run.agent_name} -> {run.result_path}")

    index_path = write_index(run_dir, runs)
    print(f"\nRun index: {index_path}")
    failures = sum(1 for run in runs if not run.success)
    return 1 if failures else 0


def main() -> int:
    args = parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
