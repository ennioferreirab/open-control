"""Claude Code backend integration for TaskExecutor.

Extracted from executor.py to keep module sizes manageable.
Contains the CCExecutorMixin class with all Claude Code specific methods:
workspace preparation, IPC server management, CC provider execution,
session resume, memory consolidation, and thread reply handling.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mc.types import (
    ActivityEventType,
    AuthorType,
    MessageType,
    TaskStatus,
    TrustLevel,
    is_cc_model,
    extract_cc_model_name,
    task_safe_id,
)

if TYPE_CHECKING:
    from mc.types import AgentData, CCTaskResult

logger = logging.getLogger(__name__)

# Lazy reference to the shared background tasks set from executor.
_background_tasks: set[asyncio.Task[None]] | None = None


def _get_background_tasks() -> set[asyncio.Task[None]]:
    """Lazily import the shared background tasks set from executor."""
    global _background_tasks
    if _background_tasks is None:
        from mc.executor import _background_tasks as _bt
        _background_tasks = _bt
    return _background_tasks


class CCExecutorMixin:
    """Mixin providing Claude Code backend methods for TaskExecutor.

    Expects the host class (TaskExecutor) to provide _bridge, _agent_gateway,
    _cron_service, _on_task_completed, _ask_user_registry, _handle_provider_error.
    """

    _bridge: Any
    _agent_gateway: Any
    _cron_service: Any
    _on_task_completed: Any
    _ask_user_registry: Any

    async def _enrich_cc_description(
        self, task_id: str, description: str | None, task_data: dict | None,
    ) -> str:
        """Enrich CC task description with file manifest, thread context, and tag attributes."""
        # Import through mc.executor to ensure test patches on
        # "mc.executor._build_thread_context" etc. take effect.
        import mc.executor as _exe
        _build_thread_context = _exe._build_thread_context
        _build_tag_attributes_context = _exe._build_tag_attributes_context
        _human_size = _exe._human_size

        description = description or ""
        try:
            safe_id = task_safe_id(task_id)
            files_dir = str(Path.home() / ".nanobot" / "tasks" / safe_id)
            try:
                fresh_task = await asyncio.to_thread(self._bridge.query, "tasks:getById", {"task_id": task_id})
                raw_files = (fresh_task or {}).get("files") or []
            except Exception:
                logger.warning("[executor] CC enrich: failed to fetch fresh task for '%s', using snapshot", task_id)
                raw_files = (task_data or {}).get("files") or []
            file_manifest = [
                {"name": f.get("name", "unknown"), "type": f.get("type", "application/octet-stream"),
                 "size": f.get("size", 0), "subfolder": f.get("subfolder", "attachments")}
                for f in raw_files
            ]
            output_dir = str(Path.home() / ".nanobot" / "tasks" / safe_id / "output")
            task_instruction = (
                f"Task workspace: {files_dir}\n"
                f"Save ALL output files (reports, summaries, generated content) to: {output_dir}\n"
                f"Do NOT save output files outside this directory."
            )
            if file_manifest:
                manifest_summary = ", ".join(f"{f['name']} ({f['subfolder']}, {_human_size(f['size'])})" for f in file_manifest)
                task_instruction += f"\nTask has {len(file_manifest)} attached file(s) at {files_dir}/attachments. File manifest: {manifest_summary}"
            description += f"\n\n{task_instruction}"
        except Exception:
            logger.warning("[executor] CC enrich: file manifest failed for '%s'", task_id, exc_info=True)
        try:
            thread_messages = await asyncio.to_thread(self._bridge.get_task_messages, task_id)
            thread_context = _build_thread_context(thread_messages)
            if thread_context:
                description += f"\n{thread_context}"
        except Exception:
            logger.warning("[executor] CC enrich: thread context failed for '%s'", task_id, exc_info=True)
        try:
            task_tags = (task_data or {}).get("tags") or []
            if task_tags:
                tag_attr_values = await asyncio.to_thread(self._bridge.query, "tagAttributeValues:getByTask", {"task_id": task_id})
                tag_attr_catalog = await asyncio.to_thread(self._bridge.query, "tagAttributes:list", {})
                tag_attrs_context = _build_tag_attributes_context(
                    task_tags,
                    tag_attr_values if isinstance(tag_attr_values, list) else [],
                    tag_attr_catalog if isinstance(tag_attr_catalog, list) else [],
                )
                if tag_attrs_context:
                    description += f"\n\n{tag_attrs_context}"
        except Exception:
            logger.warning("[executor] CC enrich: tag attributes failed for '%s'", task_id, exc_info=True)
        return description

    async def _execute_cc_task(
        self, task_id: str, title: str, description: str | None,
        agent_name: str, agent_data: "AgentData",
        trust_level: str = "autonomous", task_data: dict | None = None,
        reasoning_level: str | None = None, needs_enrichment: bool = True,
    ) -> None:
        """Execute a task using the Claude Code CLI backend."""
        from claude_code.workspace import CCWorkspaceManager
        from claude_code.provider import ClaudeCodeProvider
        from claude_code.ipc_server import MCSocketServer
        # Import from mc.executor (which re-exports from output_enricher) so that
        # test patches on "mc.executor._snapshot_output_dir" etc. take effect.
        import mc.executor as _exe
        _snapshot_output_dir = _exe._snapshot_output_dir
        _collect_output_artifacts = _exe._collect_output_artifacts
        _relocate_invalid_memory_files = _exe._relocate_invalid_memory_files
        _PROVIDER_ERRORS = _exe._PROVIDER_ERRORS

        bg_tasks = _get_background_tasks()

        # 0a. Enrich description if caller hasn't already done it
        if needs_enrichment:
            description = await self._enrich_cc_description(task_id, description, task_data)

        # 0b. Sync Convex prompt, variables, and model into agent_data
        convex_agent = await self._sync_cc_convex_agent(agent_name, agent_data)

        # Sync claudeCodeOpts from Convex if YAML/local opts are not set
        if agent_data.claude_code_opts is None and convex_agent:
            cc_raw = convex_agent.get("claude_code_opts")
            if cc_raw and isinstance(cc_raw, dict):
                from claude_code.types import ClaudeCodeOpts
                agent_data.claude_code_opts = ClaudeCodeOpts(
                    permission_mode=cc_raw.get("permission_mode", "acceptEdits"),
                    max_budget_usd=cc_raw.get("max_budget_usd"),
                    max_turns=cc_raw.get("max_turns"),
                )
                logger.info("[executor] CC: claudeCodeOpts loaded from Convex for %s: permission_mode=%s", agent_name, agent_data.claude_code_opts.permission_mode)

        # 0c. Map reasoning level to effort level
        if reasoning_level:
            effort_map = {"low": "low", "medium": "medium", "high": "high", "max": "high"}
            effort = effort_map.get(reasoning_level, "high")
            if agent_data.claude_code_opts is None:
                from claude_code.types import ClaudeCodeOpts
                agent_data.claude_code_opts = ClaudeCodeOpts()
            agent_data.claude_code_opts.effort_level = effort
            logger.info("[executor] CC: effort level set to '%s' (from reasoning '%s') for '%s'", effort, reasoning_level, agent_name)

        # 0d. Resolve board-scoped workspace
        _cc_board_name, _cc_memory_mode = await self._resolve_cc_board(task_data, agent_name, title)

        # 0e. Snapshot output dir for artifact detection
        pre_snapshot = await asyncio.to_thread(_snapshot_output_dir, task_id)

        # 1. Prepare workspace
        try:
            ws_mgr = CCWorkspaceManager()
            from mc.orientation import load_orientation
            ws_ctx = ws_mgr.prepare(
                agent_name, agent_data, task_id,
                orientation=load_orientation(agent_name),
                task_prompt=title, board_name=_cc_board_name, memory_mode=_cc_memory_mode,
            )
        except Exception as exc:
            await self._crash_task(task_id, title, f"Workspace preparation failed: {exc}", agent_name)
            return

        # 2. Start IPC server
        from mc.ask_user.handler import AskUserHandler
        ask_handler = AskUserHandler()
        ipc_server = MCSocketServer(self._bridge, None, cron_service=self._cron_service)
        ipc_server.set_ask_user_handler(ask_handler)
        if self._ask_user_registry is not None:
            self._ask_user_registry.register(task_id, ask_handler)
        try:
            await ipc_server.start(ws_ctx.socket_path)
        except Exception as exc:
            await self._crash_task(task_id, title, f"MCP IPC server failed: {exc}", agent_name)
            return

        # 3. Look up existing session for resume (CC-6 AC2)
        session_id = await self._lookup_cc_session(agent_name, task_id)

        # 4. Execute via CC provider
        try:
            from nanobot.config.loader import load_config
            _cfg = load_config()
            provider = ClaudeCodeProvider(cli_path=_cfg.claude_code.cli_path, defaults=_cfg.claude_code)
            prompt = f"{title}\n\n{description}" if description else title

            def on_stream(msg: dict) -> None:
                if msg.get("type") == "text":
                    task = asyncio.create_task(self._post_cc_activity(task_id, agent_name, msg["text"]))
                    bg_tasks.add(task)
                    task.add_done_callback(bg_tasks.discard)

            result = await provider.execute_task(
                prompt=prompt, agent_config=agent_data, task_id=task_id,
                workspace_ctx=ws_ctx, session_id=session_id, on_stream=on_stream,
            )
        except _PROVIDER_ERRORS as exc:
            await self._handle_provider_error(task_id, title, agent_name, exc)
            return
        except Exception as exc:
            await self._crash_task(task_id, title, f"Claude Code execution failed: {exc}", agent_name)
            return
        finally:
            if self._ask_user_registry is not None:
                self._ask_user_registry.unregister(task_id)
            await ipc_server.stop()

        # 5. Process result
        await asyncio.to_thread(_relocate_invalid_memory_files, task_id, ws_ctx.cwd)

        if result.is_error:
            try:
                await asyncio.to_thread(self._bridge.sync_task_output_files, task_id, task_data or {}, agent_name)
            except Exception:
                logger.warning("[executor] CC: output sync failed for errored task '%s'", title, exc_info=True)
            await self._crash_task(task_id, title, f"Claude Code error: {result.output[:1000]}", agent_name)
        else:
            await self._complete_cc_task(task_id, title, agent_name, result, trust_level=trust_level)
            try:
                artifacts = await asyncio.to_thread(_collect_output_artifacts, task_id, pre_snapshot)
                if artifacts:
                    logger.info("[executor] CC: %d artifact(s) detected for task '%s'", len(artifacts), title)
                await asyncio.to_thread(self._bridge.sync_task_output_files, task_id, task_data or {}, agent_name)
            except Exception:
                logger.warning("[executor] CC: artifact sync failed for '%s'", title, exc_info=True)
            if self._on_task_completed:
                try:
                    await self._on_task_completed(task_id, result.output or "")
                except Exception:
                    logger.exception("[executor] on_task_completed failed for CC task '%s'", title)

        # Fire-and-forget post-CC memory consolidation
        self._schedule_cc_consolidation(bg_tasks, title, task_id, result, ws_ctx.cwd)

    # ── CC helper methods ─────────────────────────────────────────────────

    async def _sync_cc_convex_agent(self, agent_name: str, agent_data: "AgentData") -> dict | None:
        """Sync Convex prompt, variables, model into agent_data. Returns convex_agent dict."""
        convex_agent: dict | None = None
        try:
            convex_agent = await asyncio.to_thread(self._bridge.get_agent_by_name, agent_name)
            if convex_agent:
                if cp := convex_agent.get("prompt"):
                    agent_data.prompt = cp
                if cm := convex_agent.get("model"):
                    if is_cc_model(cm):
                        agent_data.model = extract_cc_model_name(cm)
                        logger.info("[executor] CC: Convex model synced for '%s': %s → %s", agent_name, cm, agent_data.model)
                    else:
                        logger.info("[executor] CC: Convex model '%s' is not cc/ prefixed, keeping agent_data model", cm)
                for var in (convex_agent.get("variables") or []):
                    if agent_data.prompt:
                        agent_data.prompt = agent_data.prompt.replace("{{" + var["name"] + "}}", var["value"])
                convex_skills = convex_agent.get("skills")
                if convex_skills is not None:
                    agent_data.skills = convex_skills
        except Exception:
            logger.warning("[executor] CC: Convex agent sync failed for '%s'", agent_name)
        return convex_agent

    async def _resolve_cc_board(
        self, task_data: dict | None, agent_name: str, title: str,
    ) -> tuple[str | None, str]:
        """Resolve board-scoped workspace for CC. Returns (board_name, memory_mode)."""
        _cc_board_name: str | None = None
        _cc_memory_mode: str = "clean"
        _board_id = (task_data or {}).get("board_id")
        if _board_id:
            try:
                _board = await asyncio.to_thread(self._bridge.get_board_by_id, _board_id)
                if _board:
                    _cc_board_name = _board.get("name")
                    if _cc_board_name:
                        from mc.board_utils import get_agent_memory_mode
                        _cc_memory_mode = get_agent_memory_mode(_board, agent_name)
                        logger.info("[executor] CC: board-scoped workspace for agent '%s' on board '%s' (mode=%s)", agent_name, _cc_board_name, _cc_memory_mode)
            except Exception:
                logger.warning("[executor] CC: failed to resolve board workspace for task '%s', using global workspace", title, exc_info=True)
        return _cc_board_name, _cc_memory_mode

    async def _lookup_cc_session(self, agent_name: str, task_id: str) -> str | None:
        """Look up stored CC session for resume."""
        try:
            stored = await asyncio.to_thread(self._bridge.query, "settings:get", {"key": f"cc_session:{agent_name}:{task_id}"})
            if stored and isinstance(stored, str):
                logger.info("[executor] Resuming CC session %s for %s", stored, agent_name)
                return stored
        except Exception:
            logger.debug("[executor] No stored CC session for %s:%s", agent_name, task_id)
        return None

    async def _store_cc_session(self, agent_name: str, task_id: str, session_id: str) -> None:
        """Store CC session_id for future resume."""
        try:
            await asyncio.to_thread(self._bridge.mutation, "settings:set", {"key": f"cc_session:{agent_name}:{task_id}", "value": session_id})
            await asyncio.to_thread(self._bridge.mutation, "settings:set", {"key": f"cc_session:{agent_name}:latest", "value": session_id})
            logger.info("[executor] Stored CC session %s for agent %s task %s", session_id, agent_name, task_id)
        except Exception:
            logger.warning("[executor] Failed to store CC session ID for %s", agent_name, exc_info=True)

    def _schedule_cc_consolidation(
        self, bg_tasks: set, title: str, task_id: str, result: Any, ws_cwd: Path,
    ) -> None:
        """Schedule fire-and-forget CC memory consolidation."""
        _cc_task_status = "error" if result.is_error else "completed"

        async def _post_cc_consolidate():
            try:
                from claude_code.memory_consolidator import CCMemoryConsolidator
                from mc.types import is_tier_reference
                from mc.tier_resolver import TierResolver
                _model = "tier:standard-low"
                if is_tier_reference(_model):
                    _model = TierResolver(self._bridge).resolve_model(_model) or _model
                consolidator = CCMemoryConsolidator(ws_cwd)
                await consolidator.consolidate(
                    task_title=title, task_output=result.output or "",
                    task_status=_cc_task_status, task_id=task_id, model=_model,
                )
                logger.info("[executor] CC memory consolidation done for '%s'", title)
            except Exception:
                logger.warning("[executor] CC memory consolidation failed for '%s'", title, exc_info=True)

        _t = asyncio.create_task(_post_cc_consolidate())
        bg_tasks.add(_t)
        _t.add_done_callback(bg_tasks.discard)

    async def _post_cc_activity(self, task_id: str, agent_name: str, text: str) -> None:
        """Post a streaming text chunk as a step_started activity (best-effort)."""
        try:
            await asyncio.to_thread(
                self._bridge.create_activity, ActivityEventType.STEP_STARTED,
                text[:500], task_id, agent_name,
            )
        except Exception:
            pass  # Non-critical

    async def _complete_cc_task(
        self, task_id: str, title: str, agent_name: str,
        result: "CCTaskResult", trust_level: str = "autonomous",
    ) -> None:
        """Post completion message, cost activity, store session, and transition task status."""
        _output = result.output
        if len(_output) > 2000:
            _output = _output[:2000] + f"\n\n... [truncated, full output: {len(result.output)} chars]"
        await asyncio.to_thread(self._bridge.send_message, task_id, agent_name, AuthorType.AGENT, _output, MessageType.WORK)
        await asyncio.to_thread(self._bridge.create_activity, ActivityEventType.TASK_COMPLETED, f"Task completed. Cost: ${result.cost_usd:.4f}", task_id, agent_name)

        if result.session_id:
            await self._store_cc_session(agent_name, task_id, result.session_id)

        final_status = TaskStatus.DONE if trust_level == TrustLevel.AUTONOMOUS else TaskStatus.REVIEW
        await asyncio.to_thread(self._bridge.update_task_status, task_id, final_status, agent_name, f"Agent {agent_name} completed task '{title}'")

        # Write completion to global HEARTBEAT.md
        try:
            from filelock import FileLock
            result_snippet = (result.output or "Task completed.").strip()
            if len(result_snippet) > 1000:
                result_snippet = result_snippet[:1000] + "\n...(truncated)..."
            heartbeat_content = (
                f"\n## Mission Control Update\n\n"
                f"The task **'{title}'** (ID: `{task_id}`) assigned to **{agent_name}** "
                f"has finished with status: `{final_status}`.\n\n"
                f"### Agent's Result:\n```\n{result_snippet}\n```\n\n"
                f"Please summarize this naturally and notify the user that the task is complete.\n"
            )
            heartbeat_file = Path.home() / ".nanobot" / "workspace" / "HEARTBEAT.md"

            def _write_heartbeat() -> None:
                lock = FileLock(str(heartbeat_file) + ".lock", timeout=10)
                with lock:
                    with open(heartbeat_file, "a", encoding="utf-8") as f:
                        f.write(heartbeat_content)

            await asyncio.to_thread(_write_heartbeat)
            logger.info("[executor] CC: Written task '%s' completion to HEARTBEAT.md", title)
        except Exception as hb_exc:
            logger.warning("[executor] CC: Failed to write HEARTBEAT.md for task '%s': %s", title, hb_exc)

        self._agent_gateway.clear_retry_count(task_id)
        logger.info("[executor] CC task '%s' done (cost=$%.4f)", title, result.cost_usd)

    async def _crash_task(self, task_id: str, title: str, error: str, agent_name: str = "System") -> None:
        """Post a crash message and transition the task to CRASHED."""
        logger.error("[executor] CC task crashed: %s — %s", title, error)
        try:
            await asyncio.to_thread(self._bridge.send_message, task_id, agent_name, AuthorType.SYSTEM, f"Task crashed: {error}", MessageType.SYSTEM_EVENT)
        except Exception:
            logger.exception("[executor] Failed to post crash message for task '%s'", title)
        try:
            await asyncio.to_thread(self._bridge.update_task_status, task_id, TaskStatus.CRASHED, agent_name, f"Task crashed: {error}")
        except Exception:
            logger.exception("[executor] Failed to crash task '%s'", title)

    async def handle_cc_thread_reply(
        self, task_id: str, agent_name: str, user_message: str, agent_data: "AgentData",
    ) -> str | None:
        """Handle a user follow-up message in a CC agent's task thread (CC-6 AC3)."""
        from claude_code.workspace import CCWorkspaceManager
        from claude_code.provider import ClaudeCodeProvider
        from claude_code.ipc_server import MCSocketServer

        session_id = await self._lookup_cc_session(agent_name, task_id)

        # Resolve board-scoped workspace
        _tr_board_name: str | None = None
        _tr_memory_mode: str = "clean"
        try:
            _tr_task_data = await asyncio.to_thread(self._bridge.query, "tasks:getById", {"task_id": task_id})
            _tr_board_id = (_tr_task_data or {}).get("board_id")
            if _tr_board_id:
                _tr_board = await asyncio.to_thread(self._bridge.get_board_by_id, _tr_board_id)
                if _tr_board:
                    _tr_board_name = _tr_board.get("name")
                    if _tr_board_name:
                        from mc.board_utils import get_agent_memory_mode
                        _tr_memory_mode = get_agent_memory_mode(_tr_board, agent_name)
                        logger.info("[executor] CC thread reply: board '%s' (mode=%s)", _tr_board_name, _tr_memory_mode)
        except Exception:
            logger.warning("[executor] CC thread reply: failed to resolve board workspace for task '%s'", task_id, exc_info=True)

        # Prepare workspace and IPC server
        try:
            ws_mgr = CCWorkspaceManager()
            from mc.orientation import load_orientation
            ws_ctx = ws_mgr.prepare(
                agent_name, agent_data, task_id,
                orientation=load_orientation(agent_name), task_prompt=user_message,
                board_name=_tr_board_name, memory_mode=_tr_memory_mode,
            )
        except Exception as exc:
            logger.error("[executor] CC thread reply: workspace prep failed: %s", exc)
            return None

        from mc.ask_user.handler import AskUserHandler
        ask_handler = AskUserHandler()
        ipc_server = MCSocketServer(self._bridge, None, cron_service=self._cron_service)
        ipc_server.set_ask_user_handler(ask_handler)
        if self._ask_user_registry is not None:
            self._ask_user_registry.register(task_id, ask_handler)
        try:
            await ipc_server.start(ws_ctx.socket_path)
        except Exception as exc:
            logger.error("[executor] CC thread reply: IPC server failed: %s", exc)
            return None

        try:
            from nanobot.config.loader import load_config
            _cfg = load_config()
            provider = ClaudeCodeProvider(cli_path=_cfg.claude_code.cli_path, defaults=_cfg.claude_code)
            result = await provider.execute_task(
                prompt=user_message, agent_config=agent_data, task_id=task_id,
                workspace_ctx=ws_ctx, session_id=session_id,
            )
        except Exception as exc:
            logger.error("[executor] CC thread reply: execution failed: %s", exc)
            return None
        finally:
            if self._ask_user_registry is not None:
                self._ask_user_registry.unregister(task_id)
            await ipc_server.stop()

        if result.session_id:
            await self._store_cc_session(agent_name, task_id, result.session_id)

        # Post response back to the task thread
        if result and not result.is_error:
            _reply_output = result.output
            if len(_reply_output) > 2000:
                _reply_output = _reply_output[:2000] + f"\n\n... [truncated, full output: {len(result.output)} chars]"
            try:
                await asyncio.to_thread(self._bridge.send_message, task_id, agent_name, AuthorType.AGENT, _reply_output, MessageType.WORK)
            except Exception:
                logger.warning("[executor] CC thread reply: failed to post response for %s", agent_name)

        return result.output if not result.is_error else None
