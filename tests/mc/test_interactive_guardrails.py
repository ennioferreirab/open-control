from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INTERACTIVE_PYTHON_FILES = [
    PROJECT_ROOT / "mc" / "contexts" / "interactive" / "identity.py",
    PROJECT_ROOT / "mc" / "contexts" / "interactive" / "registry.py",
    PROJECT_ROOT / "mc" / "contexts" / "interactive" / "service.py",
    PROJECT_ROOT / "mc" / "runtime" / "interactive.py",
    PROJECT_ROOT / "mc" / "runtime" / "interactive_transport.py",
]


def test_interactive_runtime_does_not_reuse_headless_cc_session_storage() -> None:
    forbidden = ["cc_session:", "settings:set", "settings:get"]

    for filepath in INTERACTIVE_PYTHON_FILES:
        source = filepath.read_text(encoding="utf-8")
        for pattern in forbidden:
            assert pattern not in source, f"{filepath} should not reference {pattern}"


def test_interactive_runtime_does_not_overload_remote_terminal_bridge_contract() -> None:
    forbidden = ["terminalSessions:", "pendingInput", "pending_input", '"output"', "'output'"]

    for filepath in INTERACTIVE_PYTHON_FILES:
        source = filepath.read_text(encoding="utf-8")
        for pattern in forbidden:
            assert pattern not in source, f"{filepath} should not reference {pattern}"
