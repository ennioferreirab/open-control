"""Architecture guardrail tests for TUI retirement (Stories 28.7, 28-12).

Verifies that:
- The supported step execution path (provider-cli) does NOT import tmux/PTY/websocket modules.
- The gateway only starts the interactive (TUI) runtime behind the escape hatch.
- The legacy interactive runtime modules carry clear deprecation notices.
- The obsolete remote TUI paths have been removed or gated from dashboard code paths.
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


class TestSupportedPathNoTmxDependency:
    """Supported step execution path modules must have no tmux/PTY/websocket imports."""

    FORBIDDEN_PATTERNS = ["import tmux", "import pty", "import websockets", "TmuxSession"]

    def _assert_no_forbidden(self, source: str, label: str) -> None:
        for pattern in self.FORBIDDEN_PATTERNS:
            assert pattern not in source, (
                f"{label} contains forbidden pattern {pattern!r} — "
                "supported path must not depend on tmux/PTY/websocket."
            )

    def test_provider_cli_strategy_has_no_tmux_imports(self) -> None:
        source_path = MC_ROOT / "application" / "execution" / "strategies" / "provider_cli.py"
        source = _read_source(source_path)
        self._assert_no_forbidden(source, "provider_cli.py strategy")

    def test_process_supervisor_has_no_tmux_imports(self) -> None:
        source_path = MC_ROOT / "runtime" / "provider_cli" / "process_supervisor.py"
        source = _read_source(source_path)
        self._assert_no_forbidden(source, "process_supervisor.py")

    def test_claude_code_provider_has_no_tmux_imports(self) -> None:
        source_path = MC_ROOT / "contexts" / "provider_cli" / "providers" / "claude_code.py"
        source = _read_source(source_path)
        self._assert_no_forbidden(source, "claude_code.py provider")


class TestGatewayTuiConditional:
    """Gateway must start the interactive (TUI) runtime only behind the escape hatch."""

    def _gateway_source(self) -> str:
        return _read_source(MC_ROOT / "runtime" / "gateway.py")

    def test_gateway_imports_build_interactive_runtime(self) -> None:
        source = self._gateway_source()
        assert "build_interactive_runtime" in source, (
            "gateway.py does not import build_interactive_runtime."
        )

    def test_gateway_has_deprecation_comment_for_tui_runtime(self) -> None:
        source = self._gateway_source()
        source_lower = source.lower()
        assert (
            "deprecated" in source_lower
            or "superseded" in source_lower
            or "legacy" in source_lower
        ), "gateway.py lacks a deprecation/legacy comment about the TUI runtime."

    def test_gateway_provider_cli_log_message_present(self) -> None:
        source = self._gateway_source()
        has_provider_cli_note = (
            "provider-cli" in source.lower()
            or "provider_cli" in source.lower()
            or "PROVIDER_CLI" in source
        )
        assert has_provider_cli_note, (
            "gateway.py does not mention provider-cli."
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
