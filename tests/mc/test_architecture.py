"""Architecture guardrail tests for the mc package.

These tests enforce module boundary rules by scanning source files for
forbidden import patterns. They prevent accidental coupling regressions
as the codebase evolves.

Rules enforced:
1. Foundation modules (bridge, types, state_machine, thread_context) must
   NOT import from mc.gateway at top level.
2. No top-level circular imports between gateway <-> executor/step_dispatcher.
3. mc.bridge top-level imports must stay minimal (only mc.types).
4. Canonical type definitions (TaskStatus, NANOBOT_AGENT_NAME) live in mc.types.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

MC_ROOT = Path(__file__).resolve().parent.parent.parent / "mc"

# ── Helpers ──────────────────────────────────────────────────────────────


def _get_toplevel_imports(filepath: Path) -> list[str]:
    """Return import source strings that appear at module (top) level.

    Only inspects direct children of the module AST node — imports
    inside functions, methods, or if TYPE_CHECKING blocks are excluded.
    This is the appropriate check for circular-import prevention since
    function-scope imports are deferred and safe.
    """
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    modules: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
        elif isinstance(node, ast.If):
            # Skip TYPE_CHECKING blocks — they are guarded and never
            # execute at runtime, so they cannot cause circular imports.
            pass
    return modules


def _get_all_imports(filepath: Path) -> list[str]:
    """Return ALL import source strings from a Python file (any scope)."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


def _collect_py_files(directory: Path, exclude: set[str] | None = None) -> list[Path]:
    """Collect all .py files in a directory, optionally excluding file stems."""
    exclude = exclude or set()
    return [
        p
        for p in directory.rglob("*.py")
        if p.stem not in exclude and p.is_file()
    ]


# ── Rule 1: Foundation modules must not import mc.gateway (any scope) ────

FOUNDATION_MODULES = [
    "bridge", "types", "state_machine", "thread_context",
]

# Directories that form the service/domain/infrastructure layers —
# these must NEVER import from mc.gateway
PROTECTED_DIRECTORIES = ["workers", "services", "domain", "infrastructure"]

EXECUTION_RUNTIME_MODULES = [
    MC_ROOT / "step_dispatcher.py",
    MC_ROOT / "chat_handler.py",
    MC_ROOT / "cc_executor.py",
]
EXECUTION_RUNTIME_MODULES.extend(
    p
    for p in (MC_ROOT / "application" / "execution" / "strategies").rglob("*.py")
    if p.is_file() and p.name != "__init__.py"
)


@pytest.mark.parametrize("module_name", FOUNDATION_MODULES)
def test_foundation_modules_do_not_import_gateway(module_name: str) -> None:
    """Foundation modules sit below mc.gateway and must not import from it.

    These modules form the base layer of the mc package. Any import of
    mc.gateway (even at function scope) would create an undesirable
    upward dependency.
    """
    filepath = MC_ROOT / f"{module_name}.py"
    if not filepath.exists():
        pytest.skip(f"{module_name}.py does not exist")
    imports = _get_all_imports(filepath)
    gateway_imports = [
        m for m in imports
        if m == "mc.gateway" or m.startswith("mc.gateway.")
    ]
    assert gateway_imports == [], (
        f"mc/{module_name}.py imports from mc.gateway — this creates an "
        f"upward dependency from a foundation module. Found: {gateway_imports}"
    )


# ── Rule 1b: Protected directories must not import mc.gateway ─────────────

@pytest.mark.parametrize("directory", PROTECTED_DIRECTORIES)
def test_protected_directories_do_not_import_gateway(directory: str) -> None:
    """Workers, services, domain, and infrastructure must not import mc.gateway.

    These layers sit below the gateway facade and must use
    mc.infrastructure.* or mc.types directly.
    """
    dir_path = MC_ROOT / directory
    if not dir_path.exists():
        pytest.skip(f"mc/{directory}/ does not exist")
    for py_file in _collect_py_files(dir_path):
        imports = _get_all_imports(py_file)
        gateway_imports = [
            m for m in imports
            if m == "mc.gateway" or m.startswith("mc.gateway.")
        ]
        relative = py_file.relative_to(MC_ROOT.parent)
        assert gateway_imports == [], (
            f"{relative} imports from mc.gateway — "
            f"use mc.infrastructure.* or mc.types instead. Found: {gateway_imports}"
        )


# ── Rule 2: No top-level circular imports gateway <-> executor/dispatcher ──


def test_gateway_no_toplevel_executor_import() -> None:
    """mc.gateway must not import mc.executor at top level.

    Function-scope imports are acceptable (and currently used) to break
    the circular dependency. This test ensures no one accidentally
    promotes a deferred import to module level.
    """
    filepath = MC_ROOT / "gateway.py"
    if not filepath.exists():
        pytest.skip("gateway.py does not exist")
    imports = _get_toplevel_imports(filepath)
    forbidden = [
        m for m in imports
        if m in ("mc.executor", "mc.step_dispatcher")
        or m.startswith("mc.executor.")
        or m.startswith("mc.step_dispatcher.")
    ]
    assert forbidden == [], (
        f"mc/gateway.py has top-level imports from executor/step_dispatcher — "
        f"move these to function scope to avoid circular imports. Found: {forbidden}"
    )


def test_executor_no_toplevel_gateway_class_import() -> None:
    """mc.executor must not import mc.gateway classes at top level.

    mc.executor imports AgentGateway at top level (this is the current
    architecture), but it must not grow additional top-level imports from
    gateway that could tighten the coupling. AGENTS_DIR and other
    constants should be imported at function scope.
    """
    filepath = MC_ROOT / "executor.py"
    if not filepath.exists():
        pytest.skip("executor.py does not exist")
    imports = _get_toplevel_imports(filepath)
    gateway_imports = [
        m for m in imports
        if m == "mc.gateway" or m.startswith("mc.gateway.")
    ]
    # Currently mc.executor imports AgentGateway at top level.
    # This test documents the current boundary — one top-level import is OK.
    assert len(gateway_imports) <= 1, (
        f"mc/executor.py has {len(gateway_imports)} top-level mc.gateway imports "
        f"(max 1 allowed). Reduce coupling by using function-scope imports. "
        f"Found: {gateway_imports}"
    )


# ── Rule 3: mc.bridge top-level imports stay minimal ──────────────────────


def test_bridge_toplevel_only_imports_types() -> None:
    """mc.bridge top-level imports from mc/ must be limited to mc.types.

    The bridge is the Convex integration boundary. Function-scope imports
    (like mc.agent_assist for ensure_soul_md) are acceptable for optional
    features, but top-level coupling must stay minimal.
    """
    filepath = MC_ROOT / "bridge.py"
    if not filepath.exists():
        pytest.skip("bridge.py does not exist")
    imports = _get_toplevel_imports(filepath)
    mc_imports = [
        m for m in imports
        if (m == "mc" or m.startswith("mc."))
        and m not in ("mc.types",)
        and not m.startswith("mc.types.")
    ]
    assert mc_imports == [], (
        f"mc/bridge.py has top-level imports from mc modules other than mc.types — "
        f"move these to function scope. Found: {mc_imports}"
    )


# ── Rule 3b: Runtime entrypoints must not import executor internals ────────


@pytest.mark.parametrize("filepath", EXECUTION_RUNTIME_MODULES)
def test_runtime_modules_do_not_import_executor(filepath: Path) -> None:
    """Runtime-facing modules must depend on execution adapters, not executor.

    The legacy executor remains a compatibility layer. Step dispatch, chat,
    CC execution, and runner strategies should route through the stabilized
    execution modules instead of importing mc.executor internals directly.
    """
    if not filepath.exists():
        pytest.skip(f"{filepath} does not exist")

    imports = _get_all_imports(filepath)
    executor_imports = [
        m for m in imports
        if m == "mc.executor" or m.startswith("mc.executor.")
    ]
    relative = filepath.relative_to(MC_ROOT.parent)
    assert executor_imports == [], (
        f"{relative} imports from mc.executor — "
        "use mc.application.execution runtime adapters instead. "
        f"Found: {executor_imports}"
    )


def test_agent_orientation_does_not_import_executor() -> None:
    """Orientation loading should depend on infrastructure helpers, not executor."""
    filepath = MC_ROOT / "agent_orientation.py"
    if not filepath.exists():
        pytest.skip("agent_orientation.py does not exist")

    imports = _get_all_imports(filepath)
    executor_imports = [
        m for m in imports
        if m == "mc.executor" or m.startswith("mc.executor.")
    ]
    assert executor_imports == [], (
        "mc/agent_orientation.py imports from mc.executor — "
        "use mc.infrastructure.orientation_helpers instead. "
        f"Found: {executor_imports}"
    )


# ── Rule 4: Canonical type definitions live in mc.types ──────────────────


def test_nanobot_agent_name_canonical_in_types() -> None:
    """NANOBOT_AGENT_NAME must be defined in mc/types.py (the canonical source).

    Other modules may re-export it (e.g. mc/gateway.py for test compat)
    but the authoritative definition lives in mc/types.py.
    """
    types_path = MC_ROOT / "types.py"
    assert types_path.exists(), "mc/types.py must exist"
    source = types_path.read_text(encoding="utf-8")
    assert re.search(
        r'^NANOBOT_AGENT_NAME\s*=', source, re.MULTILINE
    ), "NANOBOT_AGENT_NAME must be defined in mc/types.py"


def test_task_status_canonical_in_types() -> None:
    """TaskStatus enum must be defined in mc/types.py, not elsewhere in mc/."""
    types_path = MC_ROOT / "types.py"
    assert types_path.exists()
    source = types_path.read_text(encoding="utf-8")
    assert "class TaskStatus" in source, (
        "TaskStatus must be defined in mc/types.py"
    )

    # Ensure no other mc/ module redefines TaskStatus
    for py_file in _collect_py_files(MC_ROOT, exclude={"types", "__init__"}):
        other_source = py_file.read_text(encoding="utf-8")
        assert "class TaskStatus" not in other_source, (
            f"{py_file.relative_to(MC_ROOT.parent)} redefines TaskStatus — "
            f"use 'from mc.types import TaskStatus' instead"
        )


# ── Rule 5: Orchestrator must not top-level import gateway ───────────────


def test_orchestrator_no_toplevel_gateway_import() -> None:
    """mc.orchestrator must not import mc.gateway at top level.

    mc.gateway imports mc.orchestrator.TaskOrchestrator at top level,
    so mc.orchestrator must use function-scope imports for any gateway
    access to avoid a circular import.
    """
    filepath = MC_ROOT / "orchestrator.py"
    if not filepath.exists():
        pytest.skip("orchestrator.py does not exist")
    imports = _get_toplevel_imports(filepath)
    gateway_imports = [
        m for m in imports
        if m == "mc.gateway" or m.startswith("mc.gateway.")
    ]
    assert gateway_imports == [], (
        f"mc/orchestrator.py has top-level import of mc.gateway — "
        f"this creates a circular import since gateway imports orchestrator. "
        f"Move to function scope. Found: {gateway_imports}"
    )


# ── Rule 6: No direct executor private function calls from production code ──

# Modules allowed to reference executor private functions:
#   - mc/executor.py itself (defines them)
#   - mc/application/execution/runtime.py (stable adapter layer)
#   - mc/application/execution/background_tasks.py (adapter for _background_tasks)
_EXECUTOR_PRIVATE_ALLOWED = {
    MC_ROOT / "executor.py",
    MC_ROOT / "application" / "execution" / "runtime.py",
    MC_ROOT / "application" / "execution" / "background_tasks.py",
}

# Executor private functions that must not be called from production code
_EXECUTOR_PRIVATE_PATTERNS = [
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


def test_no_direct_executor_private_calls() -> None:
    """Production code must not call executor private functions directly.

    Story 20.1 AC4: No module outside of mc/executor.py and
    mc/application/execution/runtime.py may call executor._run_agent_on_task,
    executor._collect_output_artifacts, executor._relocate_invalid_memory_files,
    or executor._background_tasks.

    The canonical path is through the runtime.py facade or ExecutionEngine.
    """
    import re as _re

    violations: list[str] = []

    for py_file in _collect_py_files(MC_ROOT):
        if py_file in _EXECUTOR_PRIVATE_ALLOWED:
            continue
        # Skip test files
        if "test" in py_file.name:
            continue

        source = py_file.read_text(encoding="utf-8")
        for pattern in _EXECUTOR_PRIVATE_PATTERNS:
            matches = _re.findall(pattern, source)
            if matches:
                relative = py_file.relative_to(MC_ROOT.parent)
                violations.append(
                    f"{relative} references {matches[0]} — "
                    "use mc.application.execution.runtime adapter instead"
                )

    assert violations == [], (
        "Direct executor private function calls found in production code:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
