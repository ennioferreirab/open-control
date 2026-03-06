"""Architectural guardrail: no internal module may import from mc.gateway.

The rule is: gateway can import services; services cannot import gateway.
Only the entry point (boot.py / __main__) and tests may import from mc.gateway.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Root of the mc/ package
MC_ROOT = Path(__file__).resolve().parents[3] / "mc"

# Modules that are ALLOWED to import from mc.gateway
# gateway.py itself (re-exports), and __init__.py (documentation-only reference)
_ALLOWED_MODULES = {"gateway.py", "__init__.py"}


def _get_mc_python_files() -> list[Path]:
    """Return all .py files under mc/, excluding __pycache__ and tests."""
    return sorted(
        p for p in MC_ROOT.rglob("*.py")
        if "__pycache__" not in str(p)
    )


def _imports_from_mc_gateway(filepath: Path) -> list[int]:
    """Return line numbers where the file imports from mc.gateway.

    Checks for:
    - ``from mc.gateway import ...``
    - ``import mc.gateway``
    """
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    violations: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("mc.gateway"):
                violations.append(node.lineno)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("mc.gateway"):
                    violations.append(node.lineno)
    return violations


class TestNoInternalGatewayImports:
    """Verify that no mc/ module (except gateway.py itself) imports from mc.gateway."""

    def test_no_service_imports_gateway(self) -> None:
        all_files = _get_mc_python_files()
        violations: list[str] = []

        for filepath in all_files:
            relative = filepath.relative_to(MC_ROOT)
            # Skip allowed modules
            if relative.name in _ALLOWED_MODULES:
                continue
            # Skip the gateway module itself
            if str(relative) == "gateway.py":
                continue

            lines = _imports_from_mc_gateway(filepath)
            if lines:
                violations.append(
                    f"  {relative} imports mc.gateway at line(s) {lines}"
                )

        if violations:
            pytest.fail(
                "Architectural violation: services must not import from mc.gateway.\n"
                "The following files violate this rule:\n"
                + "\n".join(violations)
                + "\n\nUse mc.infrastructure.config or mc.infrastructure.agent_bootstrap instead."
            )
