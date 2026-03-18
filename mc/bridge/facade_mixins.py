"""Grouped ConvexBridge façade methods extracted from mc.bridge.__init__."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mc.bridge.repositories.agents import AgentRepository
    from mc.bridge.repositories.boards import BoardRepository
    from mc.bridge.repositories.chats import ChatRepository
    from mc.bridge.repositories.messages import MessageRepository
    from mc.bridge.repositories.specs import SpecsRepository
    from mc.bridge.repositories.steps import StepRepository
    from mc.bridge.repositories.tasks import TaskRepository
    from mc.bridge.subscriptions import SubscriptionManager


class BridgeRepositoryFacadeMixin:
    """Delegating façade methods for the ConvexBridge repositories.

    Attribute stubs below are declared for type-checking only.
    At runtime they are provided by ConvexBridge which hosts this mixin.
    """

    # -- Type-checking stubs: provided by ConvexBridge at runtime --
    _tasks: TaskRepository
    _steps: StepRepository
    _messages: MessageRepository
    _agents: AgentRepository
    _boards: BoardRepository
    _chats: ChatRepository
    _specs: SpecsRepository
    _subscriptions: SubscriptionManager

    def _ensure_repos(self) -> None: ...

    def _mutation_with_retry(
        self, function_name: str, args: dict[str, Any] | None = None
    ) -> Any: ...

    def _log_state_transition(self, entity_type: str, description: str) -> None: ...

    def update_task_status(
        self,
        task_id: str,
        status: str,
        agent_name: str | None = None,
        description: str | None = None,
        awaiting_kickoff: bool | None = None,
        review_phase: str | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._tasks.update_task_status(
            task_id, status, agent_name, description, awaiting_kickoff, review_phase
        )

    def transition_task(
        self,
        task_id: str,
        *,
        from_status: str,
        to_status: str,
        expected_state_version: int,
        reason: str,
        idempotency_key: str,
        agent_name: str | None = None,
        awaiting_kickoff: bool | None = None,
        review_phase: str | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._tasks.transition_task(
            task_id,
            from_status=from_status,
            to_status=to_status,
            expected_state_version=expected_state_version,
            reason=reason,
            idempotency_key=idempotency_key,
            agent_name=agent_name,
            awaiting_kickoff=awaiting_kickoff,
            review_phase=review_phase,
        )

    def transition_task_from_snapshot(
        self,
        task_data: dict[str, Any],
        to_status: str,
        *,
        reason: str,
        agent_name: str | None = None,
        awaiting_kickoff: bool | None = None,
        review_phase: str | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._tasks.transition_task_from_snapshot(
            task_data,
            to_status,
            reason=reason,
            agent_name=agent_name,
            awaiting_kickoff=awaiting_kickoff,
            review_phase=review_phase,
            idempotency_key=idempotency_key,
        )

    def update_execution_plan(self, task_id: str, plan: dict[str, Any]) -> Any:
        self._ensure_repos()
        return self._tasks.update_execution_plan(task_id, plan)

    def patch_routing_decision(
        self,
        task_id: str,
        routing_mode: str,
        routing_decision: dict[str, Any],
    ) -> Any:
        self._ensure_repos()
        return self._tasks.patch_routing_decision(task_id, routing_mode, routing_decision)

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

    def transition_step(
        self,
        step_id: str,
        *,
        from_status: str,
        to_status: str,
        expected_state_version: int,
        reason: str,
        idempotency_key: str,
        error_message: str | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._steps.transition_step(
            step_id,
            from_status=from_status,
            to_status=to_status,
            expected_state_version=expected_state_version,
            reason=reason,
            idempotency_key=idempotency_key,
            error_message=error_message,
        )

    def transition_step_from_snapshot(
        self,
        step_data: dict[str, Any],
        to_status: str,
        *,
        reason: str,
        error_message: str | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._steps.transition_step_from_snapshot(
            step_data,
            to_status,
            reason=reason,
            error_message=error_message,
            idempotency_key=idempotency_key,
        )

    def get_step(self, step_id: str) -> dict[str, Any] | None:
        self._ensure_repos()
        return self._steps.get_step(step_id)

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
        idempotency_key: str | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._messages.send_message(
            task_id,
            author_name,
            author_type,
            content,
            message_type,
            msg_type,
            idempotency_key,
        )

    def post_step_completion(
        self,
        task_id: str,
        step_id: str,
        agent_name: str,
        content: str,
        artifacts: list[dict[str, Any]] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._messages.post_step_completion(
            task_id,
            step_id,
            agent_name,
            content,
            artifacts,
            idempotency_key,
        )

    def post_lead_agent_message(
        self,
        task_id: str,
        content: str,
        msg_type: str,
        plan_review: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._messages.post_lead_agent_message(
            task_id,
            content,
            msg_type,
            plan_review=plan_review,
            idempotency_key=idempotency_key,
        )

    def get_recent_user_messages(self, since_timestamp: str) -> list[dict[str, Any]]:
        self._ensure_repos()
        return self._messages.get_recent_user_messages(since_timestamp)

    def post_system_error(
        self,
        task_id: str,
        content: str,
        step_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        self._ensure_repos()
        return self._messages.post_system_error(task_id, content, step_id, idempotency_key)

    def sync_agent(self, agent_data: Any) -> Any:
        self._ensure_repos()
        return self._agents.sync_agent(agent_data)

    def list_agents(self) -> list[dict[str, Any]]:
        self._ensure_repos()
        return self._agents.list_agents()

    def list_active_registry_view(self) -> list[dict[str, Any]]:
        self._ensure_repos()
        return self._agents.list_active_registry_view()

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
        prompt: str | None = None,
        display_name: str | None = None,
        model: str | None = None,
        skills: list[str] | None = None,
        soul: str | None = None,
        responsibilities: list[str] | None = None,
        non_goals: list[str] | None = None,
        principles: list[str] | None = None,
        working_style: str | None = None,
        quality_rules: list[str] | None = None,
        anti_patterns: list[str] | None = None,
        output_contract: str | None = None,
        tool_policy: str | None = None,
        memory_policy: str | None = None,
        execution_policy: str | None = None,
        review_policy_ref: str | None = None,
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
            responsibilities=responsibilities,
            non_goals=non_goals,
            principles=principles,
            working_style=working_style,
            quality_rules=quality_rules,
            anti_patterns=anti_patterns,
            output_contract=output_contract,
            tool_policy=tool_policy,
            memory_policy=memory_policy,
            execution_policy=execution_policy,
            review_policy_ref=review_policy_ref,
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

    def publish_squad_graph(self, graph: dict[str, Any]) -> Any:
        self._ensure_repos()
        return self._specs.publish_squad_graph(graph)

    def subscribe(self, function_name: str, args: dict[str, Any] | None = None) -> Iterator[Any]:
        self._ensure_repos()
        return self._subscriptions.subscribe(function_name, args)

    def async_subscribe(
        self,
        function_name: str,
        args: dict[str, Any] | None = None,
        poll_interval: float = 2.0,
        sleep_controller: Any | None = None,
    ) -> Any:
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
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if task_id and not task_id.startswith("chat-"):
            args["task_id"] = task_id
        if agent_name:
            args["agent_name"] = agent_name
        result = self._mutation_with_retry("activities:create", args)
        self._log_state_transition("activity", description)
        return result
