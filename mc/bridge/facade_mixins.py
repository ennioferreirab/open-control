"""Grouped ConvexBridge façade methods extracted from mc.bridge.__init__."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator


class BridgeRepositoryFacadeMixin:
    """Delegating façade methods for the ConvexBridge repositories."""

    def update_task_status(
        self,
        task_id: str,
        status: str,
        agent_name: str | None = None,
        description: str | None = None,
        awaiting_kickoff: bool | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._tasks.update_task_status(
            task_id, status, agent_name, description, awaiting_kickoff
        )

    def update_execution_plan(self, task_id: str, plan: dict[str, Any]) -> Any:
        self._ensure_repos()
        return self._tasks.update_execution_plan(task_id, plan)

    def kick_off_task(self, task_id: str, step_count: int) -> Any:
        self._ensure_repos()
        return self._tasks.kick_off_task(task_id, step_count)

    def approve_and_kick_off(
        self, task_id: str, execution_plan: dict[str, Any] | None = None
    ) -> Any:
        self._ensure_repos()
        return self._tasks.approve_and_kick_off(task_id, execution_plan)

    def create_task_directory(self, task_id: str) -> None:
        self._ensure_repos()
        self._tasks.create_task_directory(task_id)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        self._ensure_repos()
        return self._tasks.get_task(task_id)

    def sync_task_output_files(
        self, task_id: str, task_data: dict, agent_name: str = "agent"
    ) -> None:
        self._ensure_repos()
        self._tasks.sync_task_output_files(task_id, task_data, agent_name)

    def sync_output_files_to_parent(
        self, source_task_id: str, parent_task_id: str, agent_name: str = "agent"
    ) -> None:
        self._ensure_repos()
        self._tasks.sync_output_files_to_parent(source_task_id, parent_task_id, agent_name)

    def create_step(self, step_data: dict[str, Any]) -> str:
        self._ensure_repos()
        return self._steps.create_step(step_data)

    def batch_create_steps(self, task_id: str, steps: list[dict[str, Any]]) -> list[str]:
        self._ensure_repos()
        return self._steps.batch_create_steps(task_id, steps)

    def update_step_status(
        self, step_id: str, status: str, error_message: str | None = None
    ) -> Any:
        self._ensure_repos()
        return self._steps.update_step_status(step_id, status, error_message)

    def get_steps_by_task(self, task_id: str) -> list[dict[str, Any]]:
        self._ensure_repos()
        return self._steps.get_steps_by_task(task_id)

    def check_and_unblock_dependents(self, step_id: str) -> list[str]:
        self._ensure_repos()
        return self._steps.check_and_unblock_dependents(step_id)

    def get_task_messages(self, task_id: str) -> list[dict[str, Any]]:
        self._ensure_repos()
        return self._messages.get_task_messages(task_id)

    def send_message(
        self,
        task_id: str,
        author_name: str,
        author_type: str,
        content: str,
        message_type: str,
        msg_type: str | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._messages.send_message(
            task_id, author_name, author_type, content, message_type, msg_type
        )

    def post_step_completion(
        self,
        task_id: str,
        step_id: str,
        agent_name: str,
        content: str,
        artifacts: list[dict[str, Any]] | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._messages.post_step_completion(task_id, step_id, agent_name, content, artifacts)

    def post_lead_agent_message(
        self,
        task_id: str,
        content: str,
        msg_type: str,
        plan_review: dict[str, Any] | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._messages.post_lead_agent_message(
            task_id, content, msg_type, plan_review=plan_review
        )

    def get_recent_user_messages(self, since_timestamp: str) -> list[dict[str, Any]]:
        self._ensure_repos()
        return self._messages.get_recent_user_messages(since_timestamp)

    def post_system_error(self, task_id: str, content: str, step_id: str | None = None) -> Any:
        self._ensure_repos()
        return self._messages.post_system_error(task_id, content, step_id)

    def sync_agent(self, agent_data: Any) -> Any:
        self._ensure_repos()
        return self._agents.sync_agent(agent_data)

    def list_agents(self) -> list[dict[str, Any]]:
        self._ensure_repos()
        return self._agents.list_agents()

    def get_agent_by_name(self, name: str) -> dict[str, Any] | None:
        self._ensure_repos()
        return self._agents.get_agent_by_name(name)

    def list_deleted_agents(self) -> list[dict[str, Any]]:
        self._ensure_repos()
        return self._agents.list_deleted_agents()

    def archive_agent_data(
        self,
        name: str,
        memory_content: str | None,
        history_content: str | None,
        session_data: str | None,
    ) -> None:
        self._ensure_repos()
        self._agents.archive_agent_data(name, memory_content, history_content, session_data)

    def get_agent_archive(self, name: str) -> dict[str, Any] | None:
        self._ensure_repos()
        return self._agents.get_agent_archive(name)

    def clear_agent_archive(self, name: str) -> None:
        self._ensure_repos()
        self._agents.clear_agent_archive(name)

    def deactivate_agents_except(self, active_names: list[str]) -> Any:
        self._ensure_repos()
        return self._agents.deactivate_agents_except(active_names)

    def update_agent_status(
        self, agent_name: str, status: str, description: str | None = None
    ) -> Any:
        self._ensure_repos()
        return self._agents.update_agent_status(agent_name, status, description)

    def write_agent_config(self, agent_data: dict[str, Any], agents_dir: Any) -> None:
        self._ensure_repos()
        self._agents.write_agent_config(agent_data, agents_dir)

    def get_board_by_id(self, board_id: str) -> dict[str, Any] | None:
        self._ensure_repos()
        return self._boards.get_board_by_id(board_id)

    def get_default_board(self) -> dict[str, Any] | None:
        self._ensure_repos()
        return self._boards.get_default_board()

    def ensure_default_board(self) -> Any:
        self._ensure_repos()
        return self._boards.ensure_default_board()

    def get_pending_chat_messages(self) -> list[dict[str, Any]]:
        self._ensure_repos()
        return self._chats.get_pending_chat_messages()

    def send_chat_response(
        self, agent_name: str, content: str, author_name: str | None = None
    ) -> Any:
        self._ensure_repos()
        return self._chats.send_chat_response(agent_name, content, author_name)

    def mark_chat_processing(self, chat_id: str) -> Any:
        self._ensure_repos()
        return self._chats.mark_chat_processing(chat_id)

    def mark_chat_done(self, chat_id: str) -> Any:
        self._ensure_repos()
        return self._chats.mark_chat_done(chat_id)

    # ------------------------------------------------------------------
    # Specs repository façade methods
    # ------------------------------------------------------------------

    def create_agent_spec(
        self,
        name: str,
        role: str,
        prompt: str,
        display_name: str | None = None,
        model: str | None = None,
        skills: list[str] | None = None,
        soul: str | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._specs.create_agent_spec(
            name=name,
            role=role,
            prompt=prompt,
            display_name=display_name,
            model=model,
            skills=skills,
            soul=soul,
        )

    def get_agent_spec_by_name(self, name: str) -> dict[str, Any] | None:
        self._ensure_repos()
        return self._specs.get_agent_spec_by_name(name)

    def publish_agent_spec(self, spec_id: str) -> Any:
        self._ensure_repos()
        return self._specs.publish_agent_spec(spec_id)

    def create_board_agent_binding(self, board_id: str, agent_name: str) -> Any:
        self._ensure_repos()
        return self._specs.create_board_agent_binding(board_id, agent_name)

    def subscribe(self, function_name: str, args: dict[str, Any] | None = None) -> Iterator[Any]:
        self._ensure_repos()
        return self._subscriptions.subscribe(function_name, args)

    def async_subscribe(
        self,
        function_name: str,
        args: dict[str, Any] | None = None,
        poll_interval: float = 2.0,
        sleep_controller: Any | None = None,
    ) -> "Any":
        self._ensure_repos()
        return self._subscriptions.async_subscribe(
            function_name,
            args,
            poll_interval,
            sleep_controller=sleep_controller,
        )

    def create_activity(
        self,
        event_type: str,
        description: str,
        task_id: str | None = None,
        agent_name: str | None = None,
    ) -> Any:
        args: dict[str, Any] = {
            "event_type": event_type,
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if task_id:
            args["task_id"] = task_id
        if agent_name:
            args["agent_name"] = agent_name
        result = self._mutation_with_retry("activities:create", args)
        self._log_state_transition("activity", description)
        return result
