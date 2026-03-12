"""Architecture guardrail tests for the mc package."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

MC_ROOT = Path(__file__).resolve().parent.parent.parent / "mc"

FOUNDATION_FILES = {
    "mc/bridge/__init__.py": MC_ROOT / "bridge" / "__init__.py",
    "mc/types.py": MC_ROOT / "types.py",
    "mc/domain/workflow/state_machine.py": MC_ROOT / "domain" / "workflow" / "state_machine.py",
    "mc/application/execution/thread_context.py": MC_ROOT
    / "application"
    / "execution"
    / "thread_context.py",
}

PROTECTED_DIRECTORIES = [
    "application",
    "contexts",
    "domain",
    "infrastructure",
    "memory",
]

CANONICAL_DIRECTORIES = [
    "application",
    "cli",
    "contexts",
    "domain",
    "infrastructure",
    "memory",
    "runtime",
]

REMOVED_ROOT_MODULES = {
    "ask_user",
    "cc_executor",
    "cc_step_runner",
    "chat_handler",
    "executor",
    "gateway",
    "mentions",
    "orchestrator",
    "plan_materializer",
    "plan_negotiator",
    "planner",
    "review_handler",
    "services",
    "step_dispatcher",
    "workers",
}

RUNTIME_FACING_MODULES = [
    MC_ROOT / "contexts" / "conversation" / "chat_handler.py",
    MC_ROOT / "contexts" / "execution" / "cc_executor.py",
    MC_ROOT / "contexts" / "execution" / "step_dispatcher.py",
]
RUNTIME_FACING_MODULES.extend(
    p
    for p in (MC_ROOT / "application" / "execution" / "strategies").rglob("*.py")
    if p.is_file() and p.name != "__init__.py"
)

EXECUTOR_PRIVATE_ALLOWED = {
    MC_ROOT / "contexts" / "execution" / "executor.py",
    MC_ROOT / "application" / "execution" / "runtime.py",
    MC_ROOT / "application" / "execution" / "background_tasks.py",
}

EXECUTOR_PRIVATE_PATTERNS = [
    r"executor\._run_agent_on_task",
    r"executor\._collect_output_artifacts",
    r"executor\._relocate_invalid_memory_files",
    r"executor\._background_tasks",
    r"executor\._snapshot_output_dir",
    r"executor\._make_provider",
    r"executor\._human_size",
    r"executor\._build_thread_context",
    r"executor\._build_tag_attributes_context",
]


def _get_toplevel_imports(filepath: Path) -> list[str]:
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    modules: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def _get_all_imports(filepath: Path) -> list[str]:
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def _collect_py_files(directory: Path, exclude: set[str] | None = None) -> list[Path]:
    excluded = exclude or set()
    return [
        path for path in directory.rglob("*.py") if path.is_file() and path.stem not in excluded
    ]


@pytest.mark.parametrize("relative_path", FOUNDATION_FILES)
def test_foundation_modules_do_not_import_runtime_gateway(
    relative_path: str,
) -> None:
    filepath = FOUNDATION_FILES[relative_path]
    imports = _get_all_imports(filepath)
    gateway_imports = [
        module
        for module in imports
        if module == "mc.runtime.gateway" or module.startswith("mc.runtime.gateway.")
    ]
    assert gateway_imports == [], f"{relative_path} imports mc.runtime.gateway: {gateway_imports}"


@pytest.mark.parametrize("directory", PROTECTED_DIRECTORIES)
def test_protected_directories_do_not_import_runtime_gateway(
    directory: str,
) -> None:
    dir_path = MC_ROOT / directory
    if not dir_path.exists():
        pytest.skip(f"mc/{directory}/ does not exist")

    violations: list[str] = []
    for py_file in _collect_py_files(dir_path):
        imports = _get_all_imports(py_file)
        bad = [
            module
            for module in imports
            if module == "mc.runtime.gateway" or module.startswith("mc.runtime.gateway.")
        ]
        if bad:
            violations.append(f"{py_file.relative_to(MC_ROOT.parent)}: {bad}")

    assert violations == [], "\n".join(violations)


def test_runtime_gateway_has_no_toplevel_execution_cycle_imports() -> None:
    filepath = MC_ROOT / "runtime" / "gateway.py"
    imports = _get_toplevel_imports(filepath)
    forbidden = [
        module
        for module in imports
        if module
        in (
            "mc.contexts.execution.executor",
            "mc.contexts.execution.step_dispatcher",
        )
        or module.startswith("mc.contexts.execution.executor.")
        or module.startswith("mc.contexts.execution.step_dispatcher.")
    ]
    assert forbidden == [], forbidden


def test_execution_executor_does_not_import_runtime_gateway() -> None:
    filepath = MC_ROOT / "contexts" / "execution" / "executor.py"
    imports = _get_all_imports(filepath)
    gateway_imports = [
        module
        for module in imports
        if module == "mc.runtime.gateway" or module.startswith("mc.runtime.gateway.")
    ]
    assert gateway_imports == [], gateway_imports


def test_bridge_toplevel_only_imports_types() -> None:
    filepath = MC_ROOT / "bridge" / "__init__.py"
    imports = _get_toplevel_imports(filepath)
    mc_imports = [
        module
        for module in imports
        if (module == "mc" or module.startswith("mc."))
        and not module.startswith("mc.bridge.")
        and module not in ("mc.types",)
        and not module.startswith("mc.types.")
    ]
    assert mc_imports == [], mc_imports


@pytest.mark.parametrize("filepath", RUNTIME_FACING_MODULES)
def test_runtime_facing_modules_do_not_import_executor_module(
    filepath: Path,
) -> None:
    imports = _get_all_imports(filepath)
    executor_imports = [
        module
        for module in imports
        if module == "mc.contexts.execution.executor"
        or module.startswith("mc.contexts.execution.executor.")
    ]
    relative = filepath.relative_to(MC_ROOT.parent)
    assert executor_imports == [], f"{relative}: {executor_imports}"


def test_orientation_module_does_not_import_executor_module() -> None:
    filepath = MC_ROOT / "infrastructure" / "orientation.py"
    imports = _get_all_imports(filepath)
    executor_imports = [
        module
        for module in imports
        if module == "mc.contexts.execution.executor"
        or module.startswith("mc.contexts.execution.executor.")
    ]
    assert executor_imports == [], executor_imports


def test_canonical_layers_do_not_import_removed_root_modules() -> None:
    forbidden_roots = {f"mc.{name}" for name in REMOVED_ROOT_MODULES}
    violations: list[str] = []

    for directory in CANONICAL_DIRECTORIES:
        dir_path = MC_ROOT / directory
        if not dir_path.exists():
            continue
        for py_file in _collect_py_files(dir_path):
            imports = _get_all_imports(py_file)
            bad = sorted(
                module
                for module in imports
                if module in forbidden_roots
                or any(module.startswith(f"{root}.") for root in forbidden_roots)
            )
            if bad:
                violations.append(f"{py_file.relative_to(MC_ROOT.parent)}: {bad}")

    assert violations == [], "\n".join(violations)


def test_nanobot_agent_name_canonical_in_types() -> None:
    source = (MC_ROOT / "types.py").read_text(encoding="utf-8")
    assert re.search(r"^NANOBOT_AGENT_NAME\s*=", source, re.MULTILINE)


def test_task_status_canonical_in_types() -> None:
    types_path = MC_ROOT / "types.py"
    source = types_path.read_text(encoding="utf-8")
    assert "class TaskStatus" in source

    for py_file in _collect_py_files(MC_ROOT, exclude={"types", "__init__"}):
        other_source = py_file.read_text(encoding="utf-8")
        assert "class TaskStatus" not in other_source, (
            f"{py_file.relative_to(MC_ROOT.parent)} redefines TaskStatus"
        )


def test_root_python_modules_are_minimal() -> None:
    root_modules = sorted(path.stem for path in MC_ROOT.glob("*.py") if path.is_file())
    assert root_modules == ["__init__", "types"], root_modules


@pytest.mark.parametrize(
    "directory",
    [
        "ask_user",
        "mentions",
        "services",
        "workers",
    ],
)
def test_removed_compatibility_directories_do_not_exist(directory: str) -> None:
    assert not (MC_ROOT / directory).exists(), f"mc/{directory} should be deleted"


def test_runtime_orchestrator_has_no_toplevel_gateway_import() -> None:
    filepath = MC_ROOT / "runtime" / "orchestrator.py"
    imports = _get_toplevel_imports(filepath)
    gateway_imports = [
        module
        for module in imports
        if module == "mc.runtime.gateway" or module.startswith("mc.runtime.gateway.")
    ]
    assert gateway_imports == [], gateway_imports


def test_no_direct_executor_private_calls() -> None:
    violations: list[str] = []

    for py_file in _collect_py_files(MC_ROOT):
        if py_file in EXECUTOR_PRIVATE_ALLOWED:
            continue
        source = py_file.read_text(encoding="utf-8")
        for pattern in EXECUTOR_PRIVATE_PATTERNS:
            matches = re.findall(pattern, source)
            if matches:
                relative = py_file.relative_to(MC_ROOT.parent)
                violations.append(f"{relative}: {matches[0]}")

    assert violations == [], "\n".join(violations)
