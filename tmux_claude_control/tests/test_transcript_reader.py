"""
Tests for the TranscriptReader module.

Extracted from transcript_reader.py's original __main__ self-test block.
Covers: read_all, get_last_response, get_last_user_prompt, get_tool_calls,
        tail, and timestamp filtering.
"""

import json
import os
import threading
import time
import pytest

from tmux_claude_control import ToolCall, TranscriptReader
from tmux_claude_control.transcript_reader import TranscriptEntry


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_LINES = [
    # Simple string content (user)
    json.dumps({
        "type": "user",
        "timestamp": "2026-03-02T10:00:00.000Z",
        "content": "Hello, Claude!",
    }),
    # Simple string content (assistant)
    json.dumps({
        "type": "assistant",
        "timestamp": "2026-03-02T10:00:01.000Z",
        "content": "Hello! How can I help you?",
    }),
    # tool_use entry
    json.dumps({
        "type": "tool_use",
        "timestamp": "2026-03-02T10:00:02.000Z",
        "tool_name": "bash",
        "tool_input": {"command": "ls /tmp"},
    }),
    # tool_result entry (paired with the tool_use above)
    json.dumps({
        "type": "tool_result",
        "timestamp": "2026-03-02T10:00:02.500Z",
        "tool_name": "bash",
        "tool_input": {"command": "ls /tmp"},
        "tool_output": {"result": "file1.txt\nfile2.txt"},
    }),
    # Rich array content format (user)
    json.dumps({
        "type": "user",
        "timestamp": "2026-03-02T10:00:03.000Z",
        "content": [
            {"type": "text", "text": "What files are in /tmp?"},
            {"type": "tool_result", "tool_use_id": "abc", "content": "file1\nfile2"},
        ],
    }),
    # Rich array content format (assistant)
    json.dumps({
        "type": "assistant",
        "timestamp": "2026-03-02T10:00:04.000Z",
        "content": [
            {"type": "text", "text": "I can see two files: "},
            {"type": "text", "text": "file1.txt and file2.txt."},
        ],
    }),
]


@pytest.fixture()
def transcript_file(tmp_path):
    """Write the sample JSONL content to a temp file and return a TranscriptReader."""
    path = tmp_path / "test_transcript.jsonl"
    path.write_text("\n".join(SAMPLE_LINES) + "\n", encoding="utf-8")
    return TranscriptReader(str(path)), str(path)


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestReadAll:
    """Tests for TranscriptReader.read_all()."""

    def test_returns_all_entries(self, transcript_file):
        """read_all() returns all 6 entries from the sample JSONL."""
        reader, _ = transcript_file
        entries = reader.read_all()
        assert len(entries) == 6, f"Expected 6 entries, got {len(entries)}"

    def test_entry_types(self, transcript_file):
        """Entry types match the expected sequence."""
        reader, _ = transcript_file
        entries = reader.read_all()
        types = [e.type for e in entries]
        assert types == ["user", "assistant", "tool_use", "tool_result", "user", "assistant"]


class TestGetLastResponse:
    """Tests for TranscriptReader.get_last_response()."""

    def test_last_response_plain_string(self, transcript_file):
        """get_last_response() returns text from rich array content (last assistant entry)."""
        reader, _ = transcript_file
        last_resp = reader.get_last_response()
        expected = "I can see two files: file1.txt and file2.txt."
        assert last_resp == expected, f"Unexpected response: {last_resp!r}"

    def test_last_response_empty_when_no_assistant(self, tmp_path):
        """get_last_response() returns '' when there are no assistant entries."""
        path = tmp_path / "no_assistant.jsonl"
        path.write_text(
            json.dumps({"type": "user", "timestamp": "t", "content": "hi"}) + "\n",
            encoding="utf-8",
        )
        reader = TranscriptReader(str(path))
        assert reader.get_last_response() == ""


class TestGetLastUserPrompt:
    """Tests for TranscriptReader.get_last_user_prompt()."""

    def test_last_user_prompt_rich_array(self, transcript_file):
        """get_last_user_prompt() extracts text from the rich array user entry."""
        reader, _ = transcript_file
        last_user = reader.get_last_user_prompt()
        expected = "What files are in /tmp?"
        assert last_user == expected, f"Unexpected prompt: {last_user!r}"


class TestGetToolCalls:
    """Tests for TranscriptReader.get_tool_calls()."""

    def test_returns_one_tool_call(self, transcript_file):
        """get_tool_calls() returns the single bash tool call."""
        reader, _ = transcript_file
        tool_calls = reader.get_tool_calls()
        assert len(tool_calls) == 1, f"Expected 1 tool call, got {len(tool_calls)}"

    def test_tool_call_fields(self, transcript_file):
        """The tool call has the correct name, input, and output."""
        reader, _ = transcript_file
        tc = reader.get_tool_calls()[0]
        assert tc.tool_name == "bash"
        assert tc.tool_input == {"command": "ls /tmp"}
        assert tc.tool_output == {"result": "file1.txt\nfile2.txt"}

    def test_since_timestamp_filters_out_call(self, transcript_file):
        """get_tool_calls(since_timestamp=future) returns an empty list."""
        reader, _ = transcript_file
        tc_filtered = reader.get_tool_calls(since_timestamp="2026-03-02T10:00:05.000Z")
        assert tc_filtered == [], f"Expected empty list, got {tc_filtered}"

    def test_since_timestamp_includes_call(self, transcript_file):
        """get_tool_calls(since_timestamp=past) still includes the call."""
        reader, _ = transcript_file
        tc_all = reader.get_tool_calls(since_timestamp="2026-03-02T09:00:00.000Z")
        assert len(tc_all) == 1


class TestTail:
    """Tests for TranscriptReader.tail()."""

    def test_tail_replays_last_n_and_watches(self, tmp_path):
        """tail(last_n=2) replays 2 existing entries then yields a newly appended one."""
        path = tmp_path / "tail_test.jsonl"
        path.write_text("\n".join(SAMPLE_LINES) + "\n", encoding="utf-8")
        reader = TranscriptReader(str(path))

        new_entry = json.dumps({
            "type": "assistant",
            "timestamp": "2026-03-02T10:00:10.000Z",
            "content": "Appended response!",
        })

        collected: list[TranscriptEntry] = []

        def _append_after_delay():
            time.sleep(0.4)
            with open(str(path), "a", encoding="utf-8") as fh:
                fh.write(new_entry + "\n")

        appender = threading.Thread(target=_append_after_delay, daemon=True)
        appender.start()

        gen = reader.tail(last_n=2)
        for _ in range(3):  # 2 existing + 1 new
            entry = next(gen)
            collected.append(entry)

        appender.join(timeout=3)

        assert len(collected) == 3, f"Expected 3 collected, got {len(collected)}"
        assert collected[-1].content == "Appended response!", (
            f"Unexpected tail content: {collected[-1].content!r}"
        )
