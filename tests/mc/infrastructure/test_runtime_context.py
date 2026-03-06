"""Tests for mc.infrastructure.runtime_context — RuntimeContext dataclass."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


class TestRuntimeContext:
    """RuntimeContext lightweight container."""

    def test_creation_with_bridge(self) -> None:
        from mc.infrastructure.runtime_context import RuntimeContext

        bridge = MagicMock()
        ctx = RuntimeContext(bridge=bridge)
        assert ctx.bridge is bridge

    def test_default_agents_dir(self) -> None:
        from mc.infrastructure.runtime_context import RuntimeContext

        bridge = MagicMock()
        ctx = RuntimeContext(bridge=bridge)
        assert ctx.agents_dir == Path.home() / ".nanobot" / "agents"

    def test_custom_agents_dir(self, tmp_path: Path) -> None:
        from mc.infrastructure.runtime_context import RuntimeContext

        bridge = MagicMock()
        ctx = RuntimeContext(bridge=bridge, agents_dir=tmp_path)
        assert ctx.agents_dir == tmp_path

    def test_default_admin_key_empty(self) -> None:
        from mc.infrastructure.runtime_context import RuntimeContext

        bridge = MagicMock()
        ctx = RuntimeContext(bridge=bridge)
        assert ctx.admin_key == ""

    def test_default_admin_url_empty(self) -> None:
        from mc.infrastructure.runtime_context import RuntimeContext

        bridge = MagicMock()
        ctx = RuntimeContext(bridge=bridge)
        assert ctx.admin_url == ""

    def test_custom_admin_key(self) -> None:
        from mc.infrastructure.runtime_context import RuntimeContext

        bridge = MagicMock()
        ctx = RuntimeContext(bridge=bridge, admin_key="secret-key")
        assert ctx.admin_key == "secret-key"

    def test_services_default_empty_dict(self) -> None:
        from mc.infrastructure.runtime_context import RuntimeContext

        bridge = MagicMock()
        ctx = RuntimeContext(bridge=bridge)
        assert ctx.services == {}

    def test_services_mutable(self) -> None:
        from mc.infrastructure.runtime_context import RuntimeContext

        bridge = MagicMock()
        ctx = RuntimeContext(bridge=bridge)
        ctx.services["executor"] = MagicMock()
        assert "executor" in ctx.services

    def test_all_fields(self, tmp_path: Path) -> None:
        from mc.infrastructure.runtime_context import RuntimeContext

        bridge = MagicMock()
        ctx = RuntimeContext(
            bridge=bridge,
            agents_dir=tmp_path,
            admin_key="key-123",
            admin_url="https://test.convex.cloud",
            services={"cron": MagicMock()},
        )
        assert ctx.bridge is bridge
        assert ctx.agents_dir == tmp_path
        assert ctx.admin_key == "key-123"
        assert ctx.admin_url == "https://test.convex.cloud"
        assert "cron" in ctx.services
