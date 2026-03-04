"""
transcript_reader.py

Reads Claude Code JSONL transcript files to extract actual response content.
Transcripts are written to ~/.claude/transcripts/ses_*.jsonl

Each line is JSON with format:
    {"type":"user","timestamp":"...","content":"prompt text"}
    {"type":"tool_use","timestamp":"...","tool_name":"...","tool_input":{...}}
    {"type":"tool_result","timestamp":"...","tool_name":"...","tool_input":{...},"tool_output":{...}}
    {"type":"assistant","timestamp":"...","content":"response text"}

There is also a richer format (seen in subagent transcripts) where content is an
array of objects: [{"type":"text","text":"..."}, {"type":"tool_use",...}].
Both formats are handled transparently.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TranscriptEntry:
    type: str          # "user", "assistant", "tool_use", "tool_result"
    timestamp: str
    content: str       # extracted plain text (empty string if not applicable)
    raw: dict          # the full JSON object as parsed
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    tool_output: dict = field(default_factory=dict)


@dataclass
class ToolCall:
    tool_name: str
    tool_input: dict
    timestamp: str
    tool_output: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_text(content_field) -> str:
    """
    Extract plain text from a content field that may be:
      - a plain string                   -> return as-is
      - a list of content-block dicts    -> join all "text" blocks
      - None / missing                   -> return ""
    """
    if content_field is None:
        return ""
    if isinstance(content_field, str):
        return content_field
    if isinstance(content_field, list):
        parts = []
        for block in content_field:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    # Fallback: stringify whatever we received
    return str(content_field)


def _parse_line(line: str) -> TranscriptEntry | None:
    """Parse a single JSONL line into a TranscriptEntry, or return None on error."""
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None

    entry_type = obj.get("type", "")
    timestamp = obj.get("timestamp", "")

    if entry_type in ("user", "assistant"):
        # The content field may be a string or a list of blocks.
        # For "user" entries coming from the rich format the field is sometimes
        # nested under obj["message"]["content"].
        raw_content = obj.get("content")
        if raw_content is None:
            # Try the richer format: obj["message"]["content"]
            msg = obj.get("message", {})
            raw_content = msg.get("content")
        content = _extract_text(raw_content)
        return TranscriptEntry(
            type=entry_type,
            timestamp=timestamp,
            content=content,
            raw=obj,
        )

    if entry_type == "tool_use":
        return TranscriptEntry(
            type=entry_type,
            timestamp=timestamp,
            content="",
            raw=obj,
            tool_name=obj.get("tool_name", ""),
            tool_input=obj.get("tool_input", {}),
        )

    if entry_type == "tool_result":
        # tool_output may be a dict, a list, or a plain string depending on
        # which version of the transcript format was written.
        raw_output = obj.get("tool_output", obj.get("output", {}))
        if not isinstance(raw_output, dict):
            raw_output = {"result": raw_output}
        return TranscriptEntry(
            type=entry_type,
            timestamp=timestamp,
            content="",
            raw=obj,
            tool_name=obj.get("tool_name", ""),
            tool_input=obj.get("tool_input", {}),
            tool_output=raw_output,
        )

    # Unknown / future types: preserve them with minimal parsing
    return TranscriptEntry(
        type=entry_type,
        timestamp=timestamp,
        content=_extract_text(obj.get("content")),
        raw=obj,
    )


# ---------------------------------------------------------------------------
# TranscriptReader
# ---------------------------------------------------------------------------

class TranscriptReader:
    """
    Reads Claude Code JSONL transcript files.

    Parameters
    ----------
    transcript_path:
        Explicit path to a .jsonl transcript file.  If None, the most recently
        modified file in ``~/.claude/transcripts/`` or
        ``~/.claude/projects/<sanitized-cwd>/`` is used.
    """

    _TRANSCRIPTS_DIR = Path.home() / ".claude" / "transcripts"
    _PROJECTS_DIR = Path.home() / ".claude" / "projects"

    def __init__(self, transcript_path: "str | Path | None" = None) -> None:
        if transcript_path is not None:
            self.path = Path(transcript_path)
        else:
            self.path = self._find_latest_transcript()

    # ------------------------------------------------------------------
    # Class / static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_latest_transcript() -> Path:
        """Return the most recently modified .jsonl file in the transcripts dir."""
        transcripts_dir = TranscriptReader._TRANSCRIPTS_DIR
        if not transcripts_dir.exists():
            raise FileNotFoundError(
                f"Transcripts directory not found: {transcripts_dir}"
            )
        candidates = sorted(
            transcripts_dir.glob("ses_*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError(
                f"No ses_*.jsonl transcripts found in {transcripts_dir}"
            )
        return candidates[0]

    @classmethod
    def _sanitize_path_for_projects(cls, cwd: "str | None") -> str:
        """
        Convert an absolute path to the Claude Code project-directory name.

        Claude Code stores per-project transcripts under:
            ~/.claude/projects/<sanitized-path>/
        where <sanitized-path> is the absolute path with both "/" and "_"
        replaced by "-".  Claude Code also resolves symlinks first (so on
        macOS, /tmp becomes /private/tmp).

        Example:
            /private/tmp/my_work  →  -private-tmp-my-work
            /Users/foo/bar        →  -Users-foo-bar
        """
        if not cwd:
            return ""
        p = str(Path(cwd).resolve())
        # Replace both "/" and "_" with "-" (same convention Claude Code uses)
        return p.replace("/", "-").replace("_", "-")

    @classmethod
    def detect_transcript_for_session(
        cls,
        tmux_session: str,
        cwd: "str | None" = None,
    ) -> "Path | None":
        """
        Try to find the transcript file for a given tmux session.

        Strategy:
          1. If ``cwd`` is given, look in
             ``~/.claude/projects/<sanitized-cwd>/`` for the most recently
             modified ``*.jsonl`` file (this is where recent Claude Code
             versions write project-scoped transcripts).
          2. Also check the legacy ``~/.claude/transcripts/ses_*.jsonl``
             location.
          3. Return the single most recently modified file across both
             locations, or None if neither exists.

        The file being actively written to is almost certainly the most
        recently touched one.
        """
        candidates: list[Path] = []

        # 1. Project-scoped transcripts (current Claude Code behaviour)
        if cwd:
            sanitized = cls._sanitize_path_for_projects(cwd)
            project_dir = cls._PROJECTS_DIR / sanitized
            if project_dir.exists():
                candidates.extend(project_dir.glob("*.jsonl"))

        # 2. Legacy transcripts directory
        transcripts_dir = cls._TRANSCRIPTS_DIR
        if transcripts_dir.exists():
            candidates.extend(transcripts_dir.glob("ses_*.jsonl"))

        if not candidates:
            return None

        # Return the most recently modified file across all candidates
        return max(candidates, key=lambda p: p.stat().st_mtime)

    # ------------------------------------------------------------------
    # Core read
    # ------------------------------------------------------------------

    def read_all(self) -> list[TranscriptEntry]:
        """Read every entry from the JSONL file and return as a list."""
        entries: list[TranscriptEntry] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                entry = _parse_line(line)
                if entry is not None:
                    entries.append(entry)
        return entries

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def get_last_response(self) -> str:
        """
        Return the content of the last ``assistant`` entry.

        Handles both simple string content and the richer
        ``[{"type":"text","text":"..."}]`` array format.

        Returns an empty string if no assistant entry is found.
        """
        last: str = ""
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                entry = _parse_line(line)
                if entry is not None and entry.type == "assistant":
                    last = entry.content
        return last

    def get_last_user_prompt(self) -> str:
        """
        Return the content of the last ``user`` entry.

        Returns an empty string if no user entry is found.
        """
        last: str = ""
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                entry = _parse_line(line)
                if entry is not None and entry.type == "user":
                    last = entry.content
        return last

    def get_tool_calls(
        self, since_timestamp: "str | None" = None
    ) -> list[ToolCall]:
        """
        Return all ``tool_use`` entries as ToolCall objects.

        If `since_timestamp` is given (ISO-8601 string), only entries with a
        timestamp >= that value are included.

        tool_result entries that immediately follow a tool_use are merged into
        the corresponding ToolCall's ``tool_output`` field.
        """
        entries = self.read_all()

        # Build an index of tool_result entries keyed by tool_name + position so
        # we can merge them.  We pair each tool_use with the next tool_result
        # that shares the same tool_name.
        tool_calls: list[ToolCall] = []
        used_result_indices: set[int] = set()

        for i, entry in enumerate(entries):
            if entry.type != "tool_use":
                continue
            if since_timestamp and entry.timestamp < since_timestamp:
                continue

            # Look ahead for the matching tool_result
            output: dict = {}
            for j in range(i + 1, len(entries)):
                candidate = entries[j]
                if (
                    candidate.type == "tool_result"
                    and candidate.tool_name == entry.tool_name
                    and j not in used_result_indices
                ):
                    output = candidate.tool_output
                    used_result_indices.add(j)
                    break
                # Stop searching if we hit another tool_use with the same name
                # (the result would belong to that future call, not this one)
                if candidate.type == "tool_use" and candidate.tool_name == entry.tool_name:
                    break

            tool_calls.append(
                ToolCall(
                    tool_name=entry.tool_name,
                    tool_input=entry.tool_input,
                    timestamp=entry.timestamp,
                    tool_output=output,
                )
            )

        return tool_calls

    # ------------------------------------------------------------------
    # Streaming / tailing
    # ------------------------------------------------------------------

    def tail(
        self, last_n: int = 0, poll_interval: float = 0.2
    ) -> Generator[TranscriptEntry, None, None]:
        """
        Yield TranscriptEntry objects as they are appended to the file.

        Parameters
        ----------
        last_n:
            If > 0, first yield the last `last_n` existing entries, then
            continue watching for newly appended lines.
        poll_interval:
            Seconds to wait between polling attempts (default 0.2 s).

        Usage example::

            for entry in reader.tail(last_n=5):
                print(entry)
                # break when done
        """
        with self.path.open("r", encoding="utf-8") as fh:
            # --- Replay the last N existing lines if requested ---
            if last_n > 0:
                # Collect all current lines first
                all_lines = fh.readlines()
                start = max(0, len(all_lines) - last_n)
                for line in all_lines[start:]:
                    entry = _parse_line(line)
                    if entry is not None:
                        yield entry
                # fh is now at EOF; continue watching from here
            else:
                # Seek to end so we only see new content
                fh.seek(0, 2)  # SEEK_END

            # --- Watch for new lines ---
            leftover = ""
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    time.sleep(poll_interval)
                    continue
                # Handle partial lines at the end of the chunk
                chunk = leftover + chunk
                lines = chunk.split("\n")
                # The last element may be an incomplete line
                leftover = lines[-1]
                for line in lines[:-1]:
                    entry = _parse_line(line)
                    if entry is not None:
                        yield entry

    def wait_for_response(self, timeout: float = 120.0) -> "str | None":
        """
        Block until a new ``assistant`` entry appears after the current file
        position, then return its text content.

        Parameters
        ----------
        timeout:
            Maximum seconds to wait.  Returns None if no response arrives in
            time.
        """
        deadline = time.monotonic() + timeout
        poll_interval = 0.2

        with self.path.open("r", encoding="utf-8") as fh:
            # Start watching from the current end of the file
            fh.seek(0, 2)  # SEEK_END

            leftover = ""
            while time.monotonic() < deadline:
                chunk = fh.read(65536)
                if not chunk:
                    time.sleep(poll_interval)
                    continue
                chunk = leftover + chunk
                lines = chunk.split("\n")
                leftover = lines[-1]
                for line in lines[:-1]:
                    entry = _parse_line(line)
                    if entry is not None and entry.type == "assistant":
                        return entry.content

        return None  # timed out


