"""Shared fixtures and markers for tmux_claude_control tests."""

import shutil
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--skip-claude",
        action="store_true",
        default=False,
        help="Skip tests that require a live Claude Code session",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "requires_claude: test needs live Claude Code")
    config.addinivalue_line("markers", "requires_tmux: test needs tmux installed")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--skip-claude"):
        skip_claude = pytest.mark.skip(reason="--skip-claude flag set")
        for item in items:
            if "requires_claude" in item.keywords:
                item.add_marker(skip_claude)

    if not shutil.which("tmux"):
        skip_tmux = pytest.mark.skip(reason="tmux not installed")
        for item in items:
            if "requires_tmux" in item.keywords:
                item.add_marker(skip_tmux)
