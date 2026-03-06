"""Unix socket IPC server for the MC runtime.

The MC runtime starts this server so the MCP bridge (a separate stdio subprocess)
can call MC-side tools (ask_user, send_message, delegate_task, ask_agent,
report_progress) over a local Unix socket.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.ask_user_handler import AskUserHandler
    from mc.bridge import ConvexBridge
    from nanobot.bus.queue import MessageBus

logger = logging.getLogger(__name__)

_IPC_STREAM_LIMIT = 1024 * 1024

# No timeout for ask_user — wait indefinitely for user reply.

# Maximum ask_agent recursion depth (AC6)
ASK_AGENT_MAX_DEPTH = 2


class MCSocketServer:
    """IPC server that listens on a Unix socket and dispatches to registered handlers."""

    def __init__(self, bridge: "ConvexBridge | None", bus: "MessageBus | None",
                 cron_service: Any | None = None) -> None:
        self._bridge = bridge
        self._bus = bus
        self._cron_service = cron_service
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._server: asyncio.AbstractServer | None = None
        self._socket_path: str | None = None
        self._ask_user_handler: AskUserHandler | None = None

        # Register default handlers
        self.register("ask_user", self._handle_ask_user)
        self.register("send_message", self._handle_send_message)
        self.register("delegate_task", self._handle_delegate_task)
        self.register("ask_agent", self._handle_ask_agent)
        self.register("report_progress", self._handle_report_progress)
        self.register("cron", self._handle_cron)

    # ── Registration ──────────────────────────────────────────────────

    def register(self, method: str, handler: Callable[..., Any]) -> None:
        """Register a handler for a given IPC method name."""
        self._handlers[method] = handler

    def set_ask_user_handler(self, handler: "AskUserHandler") -> None:
        """Set the ask_user handler used by the ask_user IPC method."""
        self._ask_user_handler = handler

    # ── Server lifecycle ──────────────────────────────────────────────

    async def start(self, socket_path: str) -> None:
        """Start listening on the given Unix socket path.

        Creates parent directories and removes a stale socket file if present.
        """
        if os.path.exists(socket_path):
            os.unlink(socket_path)

        self._socket_path = socket_path
        self._server = await asyncio.start_unix_server(
            self._handle_connection, path=socket_path, limit=_IPC_STREAM_LIMIT
        )
        # M2: Restrict socket to owner-only access so other local users cannot
        # connect and invoke MC operations.
        os.chmod(socket_path, 0o600)
        logger.info("MCSocketServer listening on %s", socket_path)

    async def stop(self) -> None:
        """Stop the IPC server gracefully and clean up the socket file."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            logger.info("MCSocketServer stopped")
        # L3: Clean up socket file on stop
        if self._socket_path and os.path.exists(self._socket_path):
            try:
                os.unlink(self._socket_path)
            except OSError as exc:
                logger.warning("Failed to remove socket file %s: %s", self._socket_path, exc)
            self._socket_path = None

    # ── Connection handler ────────────────────────────────────────────

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Read one request, dispatch it, and write back the response."""
        try:
            raw = await asyncio.wait_for(reader.readline(), timeout=305)
            if not raw:
                return

            request = json.loads(raw)
            method = request.get("method", "")
            params = request.get("params", {})

            handler = self._handlers.get(method)
            if handler is None:
                result: dict[str, Any] = {"error": f"Unknown method: {method}"}
            else:
                try:
                    result = await handler(**params)
                except Exception as exc:
                    logger.exception("IPC handler %s raised: %s", method, exc)
                    result = {"error": str(exc)}

            response = json.dumps(result) + "\n"
            writer.write(response.encode())
            await writer.drain()
        except Exception as exc:
            logger.warning("MCSocketServer connection error: %s", exc)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    # ── Tool handlers ─────────────────────────────────────────────────

    async def _handle_ask_user(
        self,
        question: str,
        options: list[str] | None = None,
        agent_name: str = "agent",
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Post a question to the task thread and wait for user reply."""
        if not self._bridge or not task_id:
            return {"answer": "No MC connection or task context available."}
        if not self._ask_user_handler:
            return {"answer": "No ask_user handler configured."}
        answer = await self._ask_user_handler.ask(
            question=question,
            options=options,
            agent_name=agent_name,
            task_id=task_id,
            bridge=self._bridge,
        )
        return {"answer": answer}

    async def _handle_send_message(
        self,
        content: str,
        channel: str | None = None,
        chat_id: str | None = None,
        media: list[str] | None = None,
        agent_name: str = "agent",
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Publish an outbound message to the MessageBus."""
        if self._bus and channel and chat_id:
            from nanobot.bus.events import OutboundMessage

            msg = OutboundMessage(channel=channel, chat_id=chat_id, content=content, media=media or [])
            try:
                # C2: use publish_outbound() not publish()
                await self._bus.publish_outbound(msg)
                return {"status": "Message sent"}
            except Exception as exc:
                logger.warning("send_message via bus failed: %s", exc)

        # Fallback: post to task thread if we have bridge + task_id
        if self._bridge and task_id:
            # Auto-sync media files to task output dir so sync_task_output_files picks them up
            if media and task_id:
                from mc.types import task_safe_id
                safe_id = task_safe_id(task_id)
                output_dir = Path.home() / ".nanobot" / "tasks" / safe_id / "output"
                output_dir.mkdir(parents=True, exist_ok=True)
                copied_names: list[str] = []
                for src_path in media:
                    src = Path(src_path)
                    if src.is_file():
                        try:
                            shutil.copy2(src, output_dir / src.name)
                            copied_names.append(src.name)
                        except OSError as exc:
                            logger.warning("Failed to copy media file %s: %s", src, exc)
                if copied_names:
                    content += "\n\nAttached files: " + ", ".join(copied_names)
            try:
                await asyncio.to_thread(
                    self._bridge.send_message,
                    task_id,
                    agent_name,
                    "agent",
                    content,
                    "work",
                )
                return {"status": "Message sent"}
            except Exception as exc:
                logger.warning("send_message via bridge failed: %s", exc)
                return {"error": str(exc)}

        # H3: No delivery path available — return an error instead of silently succeeding
        if not channel and not chat_id and not task_id:
            return {"error": "No delivery path: provide channel+chat_id or ensure task_id is set."}

        # H3: task_id given but no bridge — look up originating channel not feasible without bridge
        if task_id and not self._bridge:
            return {"error": "No MC connection available to deliver message."}

        return {"status": "Message sent"}

    async def _handle_delegate_task(
        self,
        description: str,
        agent: str | None = None,
        priority: str | None = None,
        agent_name: str = "agent",
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new task in Convex."""
        # Prevent self-delegation
        if agent and agent_name and agent == agent_name:
            return {
                "error": (
                    f"Self-delegation prevented: agent '{agent_name}' cannot "
                    "delegate a task to itself."
                )
            }

        if not self._bridge:
            return {"error": "No MC connection available for delegate_task."}

        task_args: dict[str, Any] = {
            "title": description[:120],
            "description": description,
        }
        if agent:
            task_args["assignedAgent"] = agent
        if agent_name:
            task_args["sourceAgent"] = agent_name
        # H4: Pass priority to Convex task creation
        if priority:
            task_args["priority"] = priority

        try:
            new_task_id = await asyncio.to_thread(
                self._bridge.mutation, "tasks:create", task_args
            )
            return {"task_id": str(new_task_id), "status": "created"}
        except Exception as exc:
            logger.exception("delegate_task failed")
            return {"error": str(exc)}

    async def _handle_ask_agent(
        self,
        agent_name: str,
        question: str,
        caller_agent: str = "agent",
        task_id: str | None = None,
        depth: int = 0,
    ) -> dict[str, Any]:
        """Create an isolated session to query a target agent.

        H2: Enforce depth limit of 2 to prevent infinite ask_agent chains.
        """
        # H2: Enforce max recursion depth
        if depth >= ASK_AGENT_MAX_DEPTH:
            return {
                "error": (
                    f"ask_agent depth limit ({ASK_AGENT_MAX_DEPTH}) exceeded. "
                    "Cannot recurse further."
                )
            }

        from mc.infrastructure.config import AGENTS_DIR
        from mc.yaml_validator import validate_agent_file

        config_file = AGENTS_DIR / agent_name / "config.yaml"
        if not config_file.exists():
            return {"error": f"Agent '{agent_name}' not found."}

        result = validate_agent_file(config_file)
        if isinstance(result, list):
            return {"error": f"Agent '{agent_name}' config invalid: {'; '.join(result)}"}

        agent_prompt = result.prompt
        agent_model = result.model
        agent_skills = result.skills

        # Resolve tier model if needed
        from mc.types import is_tier_reference
        if agent_model and is_tier_reference(agent_model):
            if self._bridge:
                try:
                    from mc.tier_resolver import TierResolver
                    agent_model = TierResolver(self._bridge).resolve_model(agent_model)
                except Exception as exc:
                    return {"error": f"Cannot resolve model tier: {exc}"}
            else:
                return {"error": f"Cannot resolve tier model '{agent_model}' without bridge."}

        try:
            from mc.provider_factory import create_provider
            provider, resolved_model = create_provider(agent_model)
        except Exception as exc:
            return {"error": f"Failed to create provider for '{agent_name}': {exc}"}

        focused_prompt = (
            f"You are being asked by {caller_agent} for clarification during task execution. "
            f"Answer concisely and specifically.\n\nQuestion: {question}"
        )
        if agent_prompt:
            focused_prompt = (
                f"[System instructions]\n{agent_prompt}\n\n"
                f"[Inter-agent query]\n{focused_prompt}"
            )

        session_key = f"mc:ask:{caller_agent}:{agent_name}:{uuid.uuid4().hex[:8]}"

        from nanobot.agent.loop import AgentLoop
        from nanobot.bus.queue import MessageBus

        workspace = AGENTS_DIR / agent_name
        workspace.mkdir(parents=True, exist_ok=True)

        bus = MessageBus()
        child_loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=workspace,
            model=resolved_model,
            allowed_skills=agent_skills,
        )

        try:
            response = await asyncio.wait_for(
                child_loop.process_direct(
                    content=focused_prompt,
                    session_key=session_key,
                    channel="mc",
                    chat_id=agent_name,
                    # H2: pass depth+1 so child ask_agent calls can enforce depth
                    extra_params={"depth": depth + 1},
                ),
                timeout=120,
            )
        except asyncio.TimeoutError:
            response = (
                f"ask_agent timed out after 120 seconds. "
                f"Agent '{agent_name}' did not respond in time."
            )
        except Exception as exc:
            response = f"ask_agent failed: {exc}"
        finally:
            # L2: Clean up bus and AgentLoop to prevent resource leaks
            try:
                await bus.close() if hasattr(bus, "close") else None
            except Exception:
                pass

        return {"response": response}

    async def _handle_report_progress(
        self,
        message: str,
        percentage: int | None = None,
        agent_name: str = "agent",
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Post a progress activity event to Convex."""
        if not self._bridge:
            return {"status": "Progress reported"}

        description = message
        if percentage is not None:
            description = f"[{percentage}%] {message}"

        # M3: use STEP_STARTED (a valid progress-type ActivityEventType) instead of "agent_output"
        from mc.types import ActivityEventType

        try:
            await asyncio.to_thread(
                self._bridge.create_activity,
                ActivityEventType.STEP_STARTED,
                description,
                task_id,
                agent_name,
            )
        except Exception as exc:
            logger.warning("report_progress failed to create activity: %s", exc)

        return {"status": "Progress reported"}

    async def _handle_cron(
        self,
        action: str = "list",
        message: str | None = None,
        every_seconds: int | None = None,
        cron_expr: str | None = None,
        tz: str | None = None,
        at: str | None = None,
        job_id: str | None = None,
        agent_name: str = "agent",
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """Proxy cron operations to the CronService."""
        if not self._cron_service:
            return {"error": "Cron service not available."}

        if action == "list":
            jobs = self._cron_service.list_jobs()
            if not jobs:
                return {"result": "No scheduled jobs."}
            lines = [f"- {j.name} (id: {j.id}, {j.schedule.kind})" for j in jobs]
            return {"result": "Scheduled jobs:\n" + "\n".join(lines)}

        elif action == "add":
            if not message:
                return {"error": "message is required for add"}
            from nanobot.cron.types import CronSchedule
            delete_after = False
            if every_seconds:
                schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
            elif cron_expr:
                if tz:
                    from zoneinfo import ZoneInfo
                    try:
                        ZoneInfo(tz)
                    except (KeyError, Exception):
                        return {"error": f"Unknown timezone '{tz}'"}
                schedule = CronSchedule(kind="cron", expr=cron_expr, tz=tz)
            elif at:
                from datetime import datetime as _dt
                try:
                    dt = _dt.fromisoformat(at)
                except ValueError:
                    return {"error": f"Invalid ISO datetime: {at}"}
                at_ms = int(dt.timestamp() * 1000)
                schedule = CronSchedule(kind="at", at_ms=at_ms)
                delete_after = True
            else:
                return {"error": "One of every_seconds, cron_expr, or at is required"}
            job = self._cron_service.add_job(
                name=message[:30],
                schedule=schedule,
                message=message,
                deliver=True,
                channel="mc",
                to=agent_name,
                delete_after_run=delete_after,
                task_id=task_id,
                agent=agent_name,
            )
            return {"result": f"Created job '{job.name}' (id: {job.id})"}

        elif action == "remove":
            if not job_id:
                return {"error": "job_id is required for remove"}
            if self._cron_service.remove_job(job_id):
                return {"result": f"Removed job {job_id}"}
            return {"error": f"Job {job_id} not found"}

        return {"error": f"Unknown cron action: {action}"}
