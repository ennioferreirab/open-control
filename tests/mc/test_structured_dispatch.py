"""Tests for structured task dispatch format (<title>+<description> tags)."""


def test_build_task_message_with_description():
    """When both title and description exist, use structured tags."""
    from mc.executor import build_task_message

    result = build_task_message("Fix login bug", "The login form rejects valid emails")
    assert result == "<title>Fix login bug</title>\n<description>The login form rejects valid emails</description>"


def test_build_task_message_without_description():
    """When no description, use plain title (backward compatible)."""
    from mc.executor import build_task_message

    result = build_task_message("Fix login bug", None)
    assert result == "Fix login bug"


def test_build_task_message_empty_description():
    """Empty string description treated as no description."""
    from mc.executor import build_task_message

    result = build_task_message("Fix login bug", "")
    assert result == "Fix login bug"
