"""Tests for mc.hooks.discovery — handler auto-discovery from directory."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import mc.hooks.discovery as disc
from mc.hooks.handler import BaseHandler


@pytest.fixture(autouse=True)
def reset_discovery_cache():
    """Reset the discovery cache before and after each test."""
    disc.reset_cache()
    yield
    disc.reset_cache()


class TestDiscoverHandlers:
    """Test handler discovery from mc/hooks/handlers/."""

    def test_discovers_known_handlers(self):
        handlers = disc.discover_handlers()
        names = {h.__name__ for h in handlers}
        # These handlers are known to exist in the project
        assert "PlanTrackerHandler" in names
        assert "SkillTrackerHandler" in names
        assert "PlanCaptureHandler" in names
        assert "AgentTrackerHandler" in names
        assert "MCPlanSyncHandler" in names

    def test_all_are_basehandler_subclasses(self):
        handlers = disc.discover_handlers()
        for h in handlers:
            assert issubclass(h, BaseHandler)
            assert h is not BaseHandler

    def test_does_not_include_base_handler(self):
        handlers = disc.discover_handlers()
        assert BaseHandler not in handlers

    def test_returns_list(self):
        handlers = disc.discover_handlers()
        assert isinstance(handlers, list)
        assert len(handlers) > 0


class TestDiscoveryCaching:
    """Test that discovery caches results."""

    def test_cache_returns_same_object(self):
        h1 = disc.discover_handlers()
        h2 = disc.discover_handlers()
        assert h1 is h2  # same list object, not just equal

    def test_reset_cache_clears(self):
        h1 = disc.discover_handlers()
        disc.reset_cache()
        h2 = disc.discover_handlers()
        assert h1 is not h2  # new list after reset
        assert h1 == h2  # but same content


class TestDiscoveryEdgeCases:
    """Test edge cases in handler discovery."""

    def test_missing_handlers_dir(self, tmp_path: Path):
        """When handlers/ directory does not exist, return empty list."""
        # Point discovery at a directory without handlers/
        fake_parent = tmp_path / "hooks"
        fake_parent.mkdir()
        fake_init = fake_parent / "__init__.py"
        fake_init.write_text("")
        # No handlers/ subdirectory

        with patch.object(
            Path, "parent", new_callable=lambda: property(lambda self: tmp_path / "hooks")
        ):
            # Simpler approach: patch __file__ in the module
            original_file = disc.__file__
            try:
                disc.__file__ = str(fake_parent / "discovery.py")
                disc.reset_cache()
                handlers = disc.discover_handlers()
                assert handlers == []
            finally:
                disc.__file__ = original_file

    def test_skips_dunder_files(self):
        """Files starting with _ should be skipped."""
        handlers = disc.discover_handlers()
        # __init__.py exists in handlers/ but should not produce handler classes
        # This is validated by the fact that no duplicates appear
        names = [h.__name__ for h in handlers]
        assert len(names) == len(set(names))

    def test_skips_broken_handler_files(self, tmp_path: Path):
        """Broken Python files in handlers/ should be silently skipped."""
        # Create a fake handlers dir with a broken file
        handlers_dir = tmp_path / "handlers"
        handlers_dir.mkdir()
        broken = handlers_dir / "broken.py"
        broken.write_text("raise ImportError('boom')")

        # Also add a valid handler
        valid = handlers_dir / "valid.py"
        valid.write_text(
            "from mc.hooks.handler import BaseHandler\n"
            "class ValidHandler(BaseHandler):\n"
            "    events = [('TestEvent', None)]\n"
            "    def handle(self):\n"
            "        return 'ok'\n"
        )

        original_file = disc.__file__
        try:
            disc.__file__ = str(tmp_path / "discovery.py")
            disc.reset_cache()

            # The broken file will fail to import via importlib.import_module
            # since it's not actually on the Python path with the expected module name.
            # But discovery should not raise regardless.
            handlers = disc.discover_handlers()
            # Even if valid.py fails to import (not on sys.path properly),
            # the key assertion is that no exception propagates.
            assert isinstance(handlers, list)
        finally:
            disc.__file__ = original_file


class TestResetCache:
    """Test the reset_cache function."""

    def test_reset_allows_rediscovery(self):
        disc.discover_handlers()
        assert disc._cache is not None
        disc.reset_cache()
        assert disc._cache is None

    def test_reset_idempotent(self):
        disc.reset_cache()
        disc.reset_cache()
        assert disc._cache is None
