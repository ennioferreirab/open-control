from __future__ import annotations

import json
from pathlib import Path

from mc.audit.memory_cohesion import (
    marker_present_in_file,
    nanobot_path_map,
    read_session_metadata,
    search_marker,
)


def test_nanobot_path_map_points_channels_and_board_to_shared_memory(tmp_path: Path) -> None:
    paths = nanobot_path_map(tmp_path, agent_name="nanobot", board_name="default")

    assert paths.shared_memory_workspace == tmp_path / "workspace"
    assert paths.global_agent_workspace == tmp_path / "agents" / "nanobot"
    assert paths.board_agent_workspace == tmp_path / "boards" / "default" / "agents" / "nanobot"
    assert paths.shared_memory_dir == tmp_path / "workspace" / "memory"
    assert paths.official_sessions_dir == tmp_path / "workspace" / "sessions"


def test_read_session_metadata_returns_first_jsonl_metadata_line(tmp_path: Path) -> None:
    session_path = tmp_path / "telegram_chat.jsonl"
    session_path.write_text(
        json.dumps(
            {
                "_type": "metadata",
                "key": "telegram:123",
                "last_consolidated": 4,
            }
        )
        + "\n"
        + json.dumps({"role": "user", "content": "hello"})
        + "\n",
        encoding="utf-8",
    )

    metadata = read_session_metadata(session_path)

    assert metadata == {
        "_type": "metadata",
        "key": "telegram:123",
        "last_consolidated": 4,
    }


def test_marker_present_in_file_detects_exact_marker(tmp_path: Path) -> None:
    target = tmp_path / "MEMORY.md"
    target.write_text("marker AUDIT_GREEN_KITE", encoding="utf-8")

    assert marker_present_in_file(target, "AUDIT_GREEN_KITE") is True
    assert marker_present_in_file(target, "AUDIT_MISSING") is False


def test_search_marker_uses_canonical_memory_store(tmp_path: Path) -> None:
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "MEMORY.md").write_text("Remember COHESION_MARKER_ALPHA", encoding="utf-8")

    result = search_marker(tmp_path, "COHESION_MARKER_ALPHA")

    assert "COHESION_MARKER_ALPHA" in result
