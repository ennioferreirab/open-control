"""Unit tests for mc.bridge.repositories modules."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mc.bridge.repositories.agents import AgentRepository
from mc.bridge.repositories.boards import BoardRepository
from mc.bridge.repositories.chats import ChatRepository
from mc.bridge.repositories.messages import MessageRepository
from mc.bridge.repositories.settings import SettingsRepository
from mc.bridge.repositories.steps import StepRepository
from mc.bridge.repositories.tasks import TaskRepository


def _make_client_mock() -> MagicMock:
    """Create a mock BridgeClient with query and mutation methods."""
    client = MagicMock()
    client.query.return_value = None
    client.mutation.return_value = None
    return client


# ── TaskRepository Tests ─────────────────────────────────────────────


class TestTaskRepository:
    def test_update_task_status(self):
        client = _make_client_mock()
        repo = TaskRepository(client)
        repo.update_task_status("task-1", "in_progress", agent_name="dev")

        client.mutation.assert_called_once_with(
            "tasks:updateStatus",
            {"task_id": "task-1", "status": "in_progress", "agent_name": "dev"},
        )

    def test_update_task_status_with_awaiting_kickoff(self):
        client = _make_client_mock()
        repo = TaskRepository(client)
        repo.update_task_status("task-1", "review", awaiting_kickoff=True)

        args = client.mutation.call_args[0][1]
        assert args["awaiting_kickoff"] is True

    def test_update_execution_plan(self):
        client = _make_client_mock()
        repo = TaskRepository(client)
        plan = {"steps": [{"title": "step1"}]}
        repo.update_execution_plan("task-1", plan)

        client.mutation.assert_called_once_with(
            "tasks:updateExecutionPlan",
            {"task_id": "task-1", "execution_plan": plan},
        )

    def test_kick_off_task(self):
        client = _make_client_mock()
        repo = TaskRepository(client)
        repo.kick_off_task("task-1", 5)

        client.mutation.assert_called_once_with(
            "tasks:kickOff",
            {"task_id": "task-1", "step_count": 5},
        )

    def test_approve_and_kick_off(self):
        client = _make_client_mock()
        repo = TaskRepository(client)
        repo.approve_and_kick_off("task-1")

        client.mutation.assert_called_once_with(
            "tasks:approveAndKickOff",
            {"task_id": "task-1"},
        )

    def test_approve_and_kick_off_with_plan(self):
        client = _make_client_mock()
        repo = TaskRepository(client)
        plan = {"steps": []}
        repo.approve_and_kick_off("task-1", execution_plan=plan)

        args = client.mutation.call_args[0][1]
        assert args["execution_plan"] == plan

    def test_get_task(self):
        client = _make_client_mock()
        client.query.return_value = {"_id": "task-1", "title": "Example"}
        repo = TaskRepository(client)

        result = repo.get_task("task-1")

        assert result == {"_id": "task-1", "title": "Example"}
        client.query.assert_called_once_with("tasks:getById", {"task_id": "task-1"})

    @patch("mc.bridge.repositories.tasks.os.makedirs")
    def test_create_task_directory(self, mock_makedirs):
        client = _make_client_mock()
        repo = TaskRepository(client)
        repo.create_task_directory("jd7abc123xyz")

        expected_base = Path.home() / ".nanobot" / "tasks" / "jd7abc123xyz"
        mock_makedirs.assert_any_call(expected_base / "attachments", exist_ok=True)
        mock_makedirs.assert_any_call(expected_base / "output", exist_ok=True)
        assert mock_makedirs.call_count == 2


# ── StepRepository Tests ─────────────────────────────────────────────


class TestStepRepository:
    def test_create_step(self):
        client = _make_client_mock()
        client.mutation.return_value = "step-123"
        repo = StepRepository(client)

        result = repo.create_step({"task_id": "t1", "title": "Do thing"})
        assert result == "step-123"
        client.mutation.assert_called_once_with(
            "steps:create", {"task_id": "t1", "title": "Do thing"}
        )

    def test_create_step_raises_on_bad_return(self):
        client = _make_client_mock()
        client.mutation.return_value = 42
        repo = StepRepository(client)

        with pytest.raises(RuntimeError, match="did not return a step id"):
            repo.create_step({"task_id": "t1"})

    def test_batch_create_steps(self):
        client = _make_client_mock()
        client.mutation.return_value = ["s1", "s2"]
        repo = StepRepository(client)

        result = repo.batch_create_steps("t1", [{"title": "a"}, {"title": "b"}])
        assert result == ["s1", "s2"]

    def test_batch_create_steps_none_return(self):
        client = _make_client_mock()
        client.mutation.return_value = None
        repo = StepRepository(client)

        result = repo.batch_create_steps("t1", [])
        assert result == []

    def test_update_step_status(self):
        client = _make_client_mock()
        repo = StepRepository(client)
        repo.update_step_status("step-1", "running")

        client.mutation.assert_called_once_with(
            "steps:updateStatus",
            {"step_id": "step-1", "status": "running"},
        )

    def test_update_step_status_with_error(self):
        client = _make_client_mock()
        repo = StepRepository(client)
        repo.update_step_status("step-1", "crashed", error_message="OOM")

        args = client.mutation.call_args[0][1]
        assert args["error_message"] == "OOM"

    def test_get_steps_by_task(self):
        client = _make_client_mock()
        client.query.return_value = [{"id": "s1"}, {"id": "s2"}]
        repo = StepRepository(client)

        result = repo.get_steps_by_task("t1")
        assert len(result) == 2
        client.query.assert_called_once_with("steps:getByTask", {"task_id": "t1"})

    def test_get_steps_by_task_empty(self):
        client = _make_client_mock()
        client.query.return_value = None
        repo = StepRepository(client)

        result = repo.get_steps_by_task("t1")
        assert result == []

    def test_check_and_unblock_dependents(self):
        client = _make_client_mock()
        client.mutation.return_value = ["s2", "s3"]
        repo = StepRepository(client)

        result = repo.check_and_unblock_dependents("s1")
        assert result == ["s2", "s3"]

    def test_check_and_unblock_dependents_none(self):
        client = _make_client_mock()
        client.mutation.return_value = None
        repo = StepRepository(client)

        result = repo.check_and_unblock_dependents("s1")
        assert result == []


# ── MessageRepository Tests ──────────────────────────────────────────


class TestMessageRepository:
    def test_get_task_messages(self):
        client = _make_client_mock()
        client.query.return_value = [{"content": "hello"}]
        repo = MessageRepository(client)

        result = repo.get_task_messages("t1")
        assert len(result) == 1
        client.query.assert_called_once_with("messages:listByTask", {"task_id": "t1"})

    def test_get_task_messages_empty(self):
        client = _make_client_mock()
        client.query.return_value = None
        repo = MessageRepository(client)

        result = repo.get_task_messages("t1")
        assert result == []

    def test_send_message(self):
        client = _make_client_mock()
        repo = MessageRepository(client)
        repo.send_message("t1", "dev", "agent", "Done!", "work")

        args = client.mutation.call_args[0][1]
        assert args["task_id"] == "t1"
        assert args["author_name"] == "dev"
        assert args["content"] == "Done!"
        assert args["message_type"] == "work"
        assert "type" not in args  # No msg_type

    def test_send_message_with_type(self):
        client = _make_client_mock()
        repo = MessageRepository(client)
        repo.send_message("t1", "dev", "agent", "Done!", "work", msg_type="step_completion")

        args = client.mutation.call_args[0][1]
        assert args["type"] == "step_completion"

    def test_post_step_completion(self):
        client = _make_client_mock()
        client.mutation.return_value = "msg-1"
        repo = MessageRepository(client)

        repo.post_step_completion("t1", "s1", "bot", "Done.")
        args = client.mutation.call_args[0][1]
        assert args["task_id"] == "t1"
        assert args["step_id"] == "s1"
        assert args["agent_name"] == "bot"
        assert "artifacts" not in args

    def test_post_step_completion_with_artifacts(self):
        client = _make_client_mock()
        repo = MessageRepository(client)
        artifacts = [{"path": "main.py", "action": "modified"}]

        repo.post_step_completion("t1", "s1", "bot", "Done.", artifacts=artifacts)
        args = client.mutation.call_args[0][1]
        assert args["artifacts"] == artifacts

    def test_post_lead_agent_message(self):
        client = _make_client_mock()
        repo = MessageRepository(client)
        repo.post_lead_agent_message("t1", "Plan text", "lead_agent_plan")

        args = client.mutation.call_args[0][1]
        assert args["type"] == "lead_agent_plan"

    def test_post_system_error(self):
        client = _make_client_mock()
        repo = MessageRepository(client)
        repo.post_system_error("t1", "Something broke", step_id="s1")

        args = client.mutation.call_args[0][1]
        assert args["task_id"] == "t1"
        assert args["author_name"] == "System"
        assert args["author_type"] == "system"
        assert args["step_id"] == "s1"

    def test_post_system_error_no_step_id(self):
        client = _make_client_mock()
        repo = MessageRepository(client)
        repo.post_system_error("t1", "Error")

        args = client.mutation.call_args[0][1]
        assert "step_id" not in args


# ── AgentRepository Tests ────────────────────────────────────────────


class TestAgentRepository:
    def test_list_agents(self):
        client = _make_client_mock()
        client.query.return_value = [{"name": "dev"}]
        repo = AgentRepository(client)

        result = repo.list_agents()
        assert result == [{"name": "dev"}]

    def test_list_agents_none(self):
        client = _make_client_mock()
        client.query.return_value = None
        repo = AgentRepository(client)

        result = repo.list_agents()
        assert result == []

    def test_get_agent_by_name(self):
        client = _make_client_mock()
        client.query.return_value = {"name": "dev", "role": "Developer"}
        repo = AgentRepository(client)

        result = repo.get_agent_by_name("dev")
        assert result == {"name": "dev", "role": "Developer"}

    def test_list_deleted_agents(self):
        client = _make_client_mock()
        client.query.return_value = [{"name": "old"}]
        repo = AgentRepository(client)

        result = repo.list_deleted_agents()
        assert result == [{"name": "old"}]

    def test_list_deleted_agents_none(self):
        client = _make_client_mock()
        client.query.return_value = None
        repo = AgentRepository(client)

        result = repo.list_deleted_agents()
        assert result == []

    def test_archive_agent_data(self):
        client = _make_client_mock()
        repo = AgentRepository(client)
        repo.archive_agent_data("dev", "mem", "hist", "sess")

        args = client.mutation.call_args[0][1]
        assert args["agent_name"] == "dev"
        assert args["memory_content"] == "mem"

    def test_get_agent_archive(self):
        client = _make_client_mock()
        client.query.return_value = {"memory_content": "data"}
        repo = AgentRepository(client)

        result = repo.get_agent_archive("dev")
        assert result == {"memory_content": "data"}

    def test_clear_agent_archive(self):
        client = _make_client_mock()
        repo = AgentRepository(client)
        repo.clear_agent_archive("dev")

        client.mutation.assert_called_once_with(
            "agents:clearAgentArchive", {"agent_name": "dev"}
        )

    def test_deactivate_agents_except(self):
        client = _make_client_mock()
        repo = AgentRepository(client)
        repo.deactivate_agents_except(["dev", "lead"])

        client.mutation.assert_called_once_with(
            "agents:deactivateExcept", {"active_names": ["dev", "lead"]}
        )

    def test_update_agent_status(self):
        client = _make_client_mock()
        repo = AgentRepository(client)
        repo.update_agent_status("dev", "active")

        client.mutation.assert_called_once_with(
            "agents:updateStatus", {"agent_name": "dev", "status": "active"}
        )


# ── BoardRepository Tests ────────────────────────────────────────────


class TestBoardRepository:
    def test_get_board_by_id(self):
        client = _make_client_mock()
        client.query.return_value = {"name": "Main"}
        repo = BoardRepository(client)

        result = repo.get_board_by_id("board-1")
        assert result == {"name": "Main"}
        client.query.assert_called_once_with("boards:getById", {"board_id": "board-1"})

    def test_ensure_default_board(self):
        client = _make_client_mock()
        client.mutation.return_value = "board-1"
        repo = BoardRepository(client)

        result = repo.ensure_default_board()
        assert result == "board-1"
        client.mutation.assert_called_once_with("boards:ensureDefaultBoard", {})


# ── ChatRepository Tests ─────────────────────────────────────────────


class TestChatRepository:
    def test_get_pending_chat_messages(self):
        client = _make_client_mock()
        client.query.return_value = [{"content": "hi"}]
        repo = ChatRepository(client)

        result = repo.get_pending_chat_messages()
        assert result == [{"content": "hi"}]

    def test_get_pending_chat_messages_empty(self):
        client = _make_client_mock()
        client.query.return_value = None
        repo = ChatRepository(client)

        result = repo.get_pending_chat_messages()
        assert result == []

    def test_send_chat_response(self):
        client = _make_client_mock()
        repo = ChatRepository(client)
        repo.send_chat_response("dev", "Hello!")

        args = client.mutation.call_args[0][1]
        assert args["agent_name"] == "dev"
        assert args["content"] == "Hello!"
        assert args["author_type"] == "agent"
        assert args["status"] == "done"

    def test_send_chat_response_with_author_name(self):
        client = _make_client_mock()
        repo = ChatRepository(client)
        repo.send_chat_response("dev", "Hello!", author_name="Developer Agent")

        args = client.mutation.call_args[0][1]
        assert args["author_name"] == "Developer Agent"

    def test_mark_chat_processing(self):
        client = _make_client_mock()
        repo = ChatRepository(client)
        repo.mark_chat_processing("chat-1")

        client.mutation.assert_called_once_with(
            "chats:updateStatus", {"chat_id": "chat-1", "status": "processing"}
        )

    def test_mark_chat_done(self):
        client = _make_client_mock()
        repo = ChatRepository(client)
        repo.mark_chat_done("chat-1")

        client.mutation.assert_called_once_with(
            "chats:updateStatus", {"chat_id": "chat-1", "status": "done"}
        )


# ── SettingsRepository Tests ─────────────────────────────────────────


class TestSettingsRepository:
    def test_init(self):
        """SettingsRepository can be instantiated."""
        client = _make_client_mock()
        repo = SettingsRepository(client)
        assert repo._client is client
