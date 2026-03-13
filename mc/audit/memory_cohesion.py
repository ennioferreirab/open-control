"""Helpers and live audit routines for memory cohesion checks."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mc.memory import create_memory_store

if TYPE_CHECKING:
    from nanobot.agent.loop import AgentLoop


@dataclass(frozen=True)
class NanobotPathMap:
    root: Path
    agent_name: str
    board_name: str
    shared_memory_workspace: Path
    shared_memory_dir: Path
    global_agent_workspace: Path
    board_agent_workspace: Path
    official_sessions_dir: Path


@dataclass(frozen=True)
class AuditCheck:
    ok: bool
    details: str


@dataclass(frozen=True)
class AuditReport:
    nanobot_paths: dict[str, str]
    official_channel: dict[str, Any]
    mc_task: dict[str, Any]
    cc_backend: dict[str, Any]
    board_artifact: dict[str, Any] | None


def nanobot_path_map(root: Path, *, agent_name: str, board_name: str) -> NanobotPathMap:
    shared_memory_workspace = root / "workspace"
    return NanobotPathMap(
        root=root,
        agent_name=agent_name,
        board_name=board_name,
        shared_memory_workspace=shared_memory_workspace,
        shared_memory_dir=shared_memory_workspace / "memory",
        global_agent_workspace=root / "agents" / agent_name,
        board_agent_workspace=root / "boards" / board_name / "agents" / agent_name,
        official_sessions_dir=shared_memory_workspace / "sessions",
    )


def read_session_metadata(session_path: Path) -> dict[str, Any]:
    if not session_path.exists():
        return {}
    with session_path.open(encoding="utf-8") as handle:
        first = handle.readline().strip()
    if not first:
        return {}
    try:
        data = json.loads(first)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def marker_present_in_file(path: Path, marker: str) -> bool:
    return path.exists() and marker in path.read_text(encoding="utf-8")


def search_marker(workspace: Path, marker: str) -> str:
    store = create_memory_store(workspace)
    index = getattr(store, "_index", None)
    if index is not None:
        index.sync()
    return store.search(marker, top_k=5)


def optional_search_marker(workspace: Path, marker: str) -> str:
    if not workspace.exists():
        return ""
    return search_marker(workspace, marker)


async def _run_nanobot_turn(
    *,
    workspace: Path,
    memory_workspace: Path,
    artifacts_workspace: Path,
    agent_name: str,
    model: str,
    channel: str,
    chat_id: str,
    prompt: str,
    session_key: str | None = None,
) -> tuple[AgentLoop, str]:
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.events import InboundMessage
    from nanobot.bus.queue import MessageBus

    from mc.infrastructure.providers.factory import create_provider

    provider, resolved_model = create_provider(model)
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=workspace,
        memory_workspace=memory_workspace,
        artifacts_workspace=artifacts_workspace,
        agent_name=agent_name,
        model=resolved_model,
    )
    response = await loop._process_message(  # noqa: SLF001
        InboundMessage(
            channel=channel,
            sender_id="audit-user",
            chat_id=chat_id,
            content=prompt,
        ),
        session_key=session_key,
    )
    return loop, response.content if response is not None else ""


async def audit_memory_cohesion(
    *,
    root: Path,
    nanobot_model: str,
    cc_model: str,
    board_name: str = "default",
    nanobot_agent: str = "nanobot",
    cc_agent: str = "offer-strategist",
    base_url: str | None = None,
    artifact_upload_path: Path | None = None,
) -> AuditReport:
    from nanobot.bus.events import InboundMessage

    from mc.artifacts import resolve_board_artifacts_workspace
    from mc.memory.service import consolidate_task_output

    paths = nanobot_path_map(root, agent_name=nanobot_agent, board_name=board_name)
    paths.shared_memory_dir.mkdir(parents=True, exist_ok=True)
    paths.global_agent_workspace.mkdir(parents=True, exist_ok=True)

    artifacts_workspace = resolve_board_artifacts_workspace(board_name, root=root)

    official_marker = f"AUDIT_TELEGRAM_{uuid.uuid4().hex[:10].upper()}"
    official_prompt = (
        f"Remember the exact marker {official_marker} and reply only with "
        f"`stored {official_marker}`."
    )
    official_chat_id = "audit-telegram"
    official_session_key = f"telegram:{official_chat_id}"
    official_loop, official_reply = await _run_nanobot_turn(
        workspace=paths.global_agent_workspace,
        memory_workspace=paths.shared_memory_workspace,
        artifacts_workspace=artifacts_workspace,
        agent_name=nanobot_agent,
        model=nanobot_model,
        channel="telegram",
        chat_id=official_chat_id,
        prompt=official_prompt,
        session_key=official_session_key,
    )
    await official_loop._process_message(  # noqa: SLF001
        InboundMessage(
            channel="telegram",
            sender_id="audit-user",
            chat_id=official_chat_id,
            content="/new",
        ),
        session_key=official_session_key,
    )

    official_session_path = paths.official_sessions_dir / "telegram_audit-telegram.jsonl"
    official_search = search_marker(paths.shared_memory_workspace, official_marker)
    official_global_search = optional_search_marker(paths.global_agent_workspace, official_marker)
    official_board_search = optional_search_marker(paths.board_agent_workspace, official_marker)
    official_memory = marker_present_in_file(paths.shared_memory_dir / "MEMORY.md", official_marker)
    official_history = marker_present_in_file(
        paths.shared_memory_dir / "HISTORY.md", official_marker
    )

    mc_marker = f"AUDIT_MC_{uuid.uuid4().hex[:10].upper()}"
    mc_session_key = f"mc:task:{nanobot_agent}:audit"
    mc_prompt = f"Remember the exact marker {mc_marker} and reply only with `stored {mc_marker}`."
    mc_loop, mc_reply = await _run_nanobot_turn(
        workspace=paths.global_agent_workspace,
        memory_workspace=paths.shared_memory_workspace,
        artifacts_workspace=artifacts_workspace,
        agent_name=nanobot_agent,
        model=nanobot_model,
        channel="mc",
        chat_id="audit-task",
        prompt=mc_prompt,
        session_key=mc_session_key,
    )
    await mc_loop.end_task_session(mc_session_key)
    mc_search = search_marker(paths.shared_memory_workspace, mc_marker)
    mc_global_search = optional_search_marker(paths.global_agent_workspace, mc_marker)
    mc_board_search = optional_search_marker(paths.board_agent_workspace, mc_marker)
    mc_memory = marker_present_in_file(paths.shared_memory_dir / "MEMORY.md", mc_marker)
    mc_history = marker_present_in_file(paths.shared_memory_dir / "HISTORY.md", mc_marker)

    cc_marker = f"AUDIT_CC_{uuid.uuid4().hex[:10].upper()}"
    cc_workspace = root / "agents" / cc_agent
    cc_workspace.mkdir(parents=True, exist_ok=True)
    cc_ok = await consolidate_task_output(
        cc_workspace,
        task_title="memory cohesion audit",
        task_output=f"Persist the exact marker {cc_marker} for future recall.",
        task_status="completed",
        task_id=f"audit-{uuid.uuid4().hex[:8]}",
        model=cc_model,
    )
    cc_search = search_marker(cc_workspace, cc_marker)
    cc_memory = marker_present_in_file(cc_workspace / "memory" / "MEMORY.md", cc_marker)
    cc_history = marker_present_in_file(cc_workspace / "memory" / "HISTORY.md", cc_marker)

    board_artifact_payload: dict[str, Any] | None = None
    if artifact_upload_path is not None and base_url is not None:
        import httpx

        with artifact_upload_path.open("rb") as handle:
            response = httpx.post(
                f"{base_url.rstrip('/')}/api/boards/{board_name}/artifacts",
                files={"files": (artifact_upload_path.name, handle, "application/octet-stream")},
                timeout=30.0,
            )
        uploaded = response.json()
        uploaded_path = artifacts_workspace / artifact_upload_path.name
        board_artifact_payload = {
            "status_code": response.status_code,
            "response": uploaded,
            "exists_on_disk": uploaded_path.exists(),
            "path": str(uploaded_path),
        }

    return AuditReport(
        nanobot_paths={
            key: str(value) for key, value in asdict(paths).items() if isinstance(value, Path)
        },
        official_channel={
            "reply": official_reply,
            "marker": official_marker,
            "memory_contains_marker": official_memory,
            "history_contains_marker": official_history,
            "search_contains_marker": official_marker in official_search,
            "global_agent_search_contains_marker": official_marker in official_global_search,
            "board_agent_search_contains_marker": official_marker in official_board_search,
            "session_metadata": read_session_metadata(official_session_path),
            "session_path": str(official_session_path),
        },
        mc_task={
            "reply": mc_reply,
            "marker": mc_marker,
            "memory_contains_marker": mc_memory,
            "history_contains_marker": mc_history,
            "search_contains_marker": mc_marker in mc_search,
            "global_agent_search_contains_marker": mc_marker in mc_global_search,
            "board_agent_search_contains_marker": mc_marker in mc_board_search,
        },
        cc_backend={
            "ok": cc_ok,
            "marker": cc_marker,
            "memory_contains_marker": cc_memory,
            "history_contains_marker": cc_history,
            "search_contains_marker": cc_marker in cc_search,
        },
        board_artifact=board_artifact_payload,
    )


def render_report_markdown(report: AuditReport) -> str:
    lines = [
        "# Memory Cohesion Audit",
        "",
        "## Nanobot Paths",
    ]
    for key, value in report.nanobot_paths.items():
        lines.append(f"- {key}: `{value}`")

    for section_name, payload in (
        ("Official Channel", report.official_channel),
        ("MC Task", report.mc_task),
        ("CC Backend", report.cc_backend),
    ):
        lines.extend(["", f"## {section_name}"])
        for key, value in payload.items():
            lines.append(f"- {key}: `{value}`")

    if report.board_artifact is not None:
        lines.extend(["", "## Board Artifact"])
        for key, value in report.board_artifact.items():
            lines.append(f"- {key}: `{value}`")

    return "\n".join(lines) + "\n"
