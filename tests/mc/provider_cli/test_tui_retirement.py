"""Architecture guardrail tests for TUI retirement (Story 28.7).

Verifies that the obsolete remote TUI paths have been removed or gated from the
primary user-facing code paths, and that the provider CLI live-share model is
the only supported path.
"""

from __future__ import annotations

import pathlib

REPO_ROOT = pathlib.Path(__file__).parents[3]
DASHBOARD_ROOT = REPO_ROOT / "dashboard"
MC_ROOT = REPO_ROOT / "mc"


def _read_source(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


class TestInteractiveChatTabsNoTuiDependency:
    """InteractiveChatTabs must not import or render InteractiveTerminalPanel."""

    def test_does_not_import_terminal_panel(self) -> None:
        source_path = (
            DASHBOARD_ROOT / "features" / "interactive" / "components" / "InteractiveChatTabs.tsx"
        )
        source = _read_source(source_path)
        import_present = any(
            "InteractiveTerminalPanel" in line
            for line in source.splitlines()
            if line.strip().startswith("import")
        )
        assert not import_present, "InteractiveChatTabs.tsx still imports InteractiveTerminalPanel."
        assert "<InteractiveTerminalPanel" not in source, (
            "InteractiveChatTabs.tsx still renders <InteractiveTerminalPanel>."
        )

    def test_has_no_tui_tab(self) -> None:
        source_path = (
            DASHBOARD_ROOT / "features" / "interactive" / "components" / "InteractiveChatTabs.tsx"
        )
        source = _read_source(source_path)
        # Check for functional TUI tab usage (not just mentions in comments)
        functional_lines = [
            line for line in source.splitlines()
            if not line.strip().startswith("*") and not line.strip().startswith("//")
        ]
        functional_source = "\n".join(functional_lines)
        assert '"TUI"' not in functional_source and "'TUI'" not in functional_source, (
            "InteractiveChatTabs.tsx still contains a functional TUI tab button."
        )

    def test_has_no_active_tui_type(self) -> None:
        source_path = (
            DASHBOARD_ROOT / "features" / "interactive" / "components" / "InteractiveChatTabs.tsx"
        )
        source = _read_source(source_path)
        assert '"tui"' not in source and "'tui'" not in source, (
            "InteractiveChatTabs.tsx still has 'tui' as an ActiveTab type."
        )


class TestBackendDeprecationNotices:
    """Interactive runtime modules that are superseded must be clearly marked."""

    def test_interactive_transport_has_deprecation_notice(self) -> None:
        source_path = MC_ROOT / "runtime" / "interactive_transport.py"
        source = _read_source(source_path)
        assert "deprecated" in source.lower() or "superseded" in source.lower(), (
            "mc/runtime/interactive_transport.py lacks a deprecation notice."
        )

    def test_interactive_runtime_has_deprecation_note(self) -> None:
        source_path = MC_ROOT / "runtime" / "interactive.py"
        source = _read_source(source_path)
        assert "deprecated" in source.lower() or "superseded" in source.lower(), (
            "mc/runtime/interactive.py lacks a deprecation note."
        )


class TestProviderCliModulesNoPtyDependency:
    """Provider CLI modules must not depend on PTY/websocket/tmux."""

    def _find_provider_cli_sources(self) -> list[pathlib.Path]:
        providers_dir = MC_ROOT / "contexts" / "provider_cli" / "providers"
        if providers_dir.exists():
            return list(providers_dir.rglob("*.py"))
        return []

    def test_provider_cli_parsers_do_not_import_interactive_transport(self) -> None:
        sources = self._find_provider_cli_sources()
        violations: list[str] = []
        for path in sources:
            content = _read_source(path)
            if "interactive_transport" in content:
                violations.append(str(path.relative_to(REPO_ROOT)))
        assert not violations, (
            "Provider CLI parser files import from interactive_transport:\n"
            + "\n".join(f"  {v}" for v in violations)
        )

    def test_provider_cli_parsers_have_no_pty_imports(self) -> None:
        forbidden = ["import pty", "import websockets", "import tmux", "TmuxSession"]
        sources = self._find_provider_cli_sources()
        violations: list[str] = []
        for path in sources:
            content = _read_source(path)
            for pattern in forbidden:
                if pattern in content:
                    violations.append(f"{path.relative_to(REPO_ROOT)}: contains '{pattern}'")
        assert not violations, (
            "Provider CLI parser files contain PTY/websocket/tmux references:\n"
            + "\n".join(f"  {v}" for v in violations)
        )

    def test_interactive_transport_not_imported_by_new_modules(self) -> None:
        allowed_importers = {"mc/runtime/interactive.py"}
        violations: list[str] = []
        for py_file in MC_ROOT.rglob("*.py"):
            rel = py_file.relative_to(REPO_ROOT).as_posix()
            if rel in allowed_importers:
                continue
            content = _read_source(py_file)
            for line in content.splitlines():
                stripped = line.strip()
                if "interactive_transport" in stripped and stripped.startswith(
                    ("import ", "from ")
                ):
                    violations.append(rel)
                    break
        assert not violations, (
            "These modules import interactive_transport outside allowed legacy wiring:\n"
            + "\n".join(f"  {v}" for v in violations)
        )
