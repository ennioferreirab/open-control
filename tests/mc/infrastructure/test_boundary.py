"""Guardrail: internal modules must not import the runtime gateway directly."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

MC_ROOT = Path(__file__).resolve().parents[3] / "mc"
ALLOWED_RELATIVE_PATHS = {
    Path("__init__.py"),
    Path("runtime/__init__.py"),
    Path("runtime/gateway.py"),
}


def _imports_from_runtime_gateway(filepath: Path) -> list[int]:
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    violations: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("mc.runtime.gateway"):
                violations.append(node.lineno)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("mc.runtime.gateway"):
                    violations.append(node.lineno)
    return violations


def test_no_internal_module_imports_runtime_gateway() -> None:
    violations: list[str] = []

    for filepath in sorted(MC_ROOT.rglob("*.py")):
        if "__pycache__" in str(filepath):
            continue
        relative = filepath.relative_to(MC_ROOT)
        if relative in ALLOWED_RELATIVE_PATHS:
            continue
        lines = _imports_from_runtime_gateway(filepath)
        if lines:
            violations.append(f"{relative}: {lines}")

    assert violations == [], (
        "Internal modules must not import mc.runtime.gateway directly.\n"
        + "\n".join(violations)
    )
