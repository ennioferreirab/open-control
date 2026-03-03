"""Session-scoped fixtures shared across all test modules."""

import pytest


@pytest.fixture(scope="session", autouse=True)
def _preimport_heavy_modules():
    """Pre-warm Python's import cache for heavy dependencies.

    litellm's first import on Python 3.13 triggers slow filesystem stat()
    calls on venv bytecode files.  Session fixtures run before any per-test
    timeout starts, so importing here ensures every test file sees a warm
    import cache — regardless of execution order or file isolation.
    """
    import mc.executor  # noqa: F401
