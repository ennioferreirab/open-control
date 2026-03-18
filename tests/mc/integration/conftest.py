"""Shared fixtures for integration tests requiring a running Convex backend."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

CONVEX_URL = "http://127.0.0.1:3210"
CONVEX_CONFIG_PATH = (
    Path(__file__).resolve().parents[3]
    / "dashboard"
    / ".convex"
    / "local"
    / "default"
    / "config.json"
)


def _convex_reachable() -> bool:
    """Check if Convex local backend is reachable."""
    try:
        urllib.request.urlopen(CONVEX_URL, timeout=2)
        return True
    except Exception:
        return False


def _read_admin_key() -> str | None:
    """Read admin key from Convex local config."""
    try:
        data = json.loads(CONVEX_CONFIG_PATH.read_text())
        return data.get("adminKey")
    except Exception:
        return None


requires_convex = pytest.mark.skipif(
    not _convex_reachable() or not _read_admin_key(),
    reason="Convex local backend not reachable or admin key not found",
)


@pytest.fixture(scope="module")
def real_bridge() -> Generator[Any, None, None]:
    """Create a real ConvexBridge connected to localhost Convex."""
    from mc.bridge import ConvexBridge

    admin_key = _read_admin_key()
    assert admin_key, "Cannot create bridge: admin key not found"
    bridge = ConvexBridge(CONVEX_URL, admin_key)
    yield bridge
    bridge.close()


@pytest.fixture(scope="module")
def default_board_id(real_bridge: Any) -> str:
    """Ensure a default board exists and return its ID."""
    board_id = real_bridge.ensure_default_board()
    assert board_id, "Failed to ensure default board"
    return board_id


@pytest.fixture
def fixture_output_dir() -> Path:
    """Return the path to the integration test fixtures directory, creating it if needed."""
    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    return fixtures_dir
