"""Unit tests for planner execution-plan generation and validation."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from nanobot.mc.planner import TaskPlanner, _build_file_summary, _parse_plan_response
from nanobot.mc.types import AgentData, ExecutionPlan, ExecutionPlanStep, NANOBOT_AGENT_NAME, LEAD_AGENT_NAME


def _agent(name: str, skills: list[str] | None = None) -> AgentData:
    return AgentData(
        name=name,
        display_name=name,
        role="Test",
        skills=skills or [],
    )


def test_parse_plan_response_new_execution_plan_fields() -> None:
    raw = json.dumps(
        {
            "steps": [
                {
                    "tempId": "step_1",
                    "title": "Extract data",
                    "description": "Extract invoice data from PDF",
                    "assignedAgent": "finance-agent",
                    "blockedBy": [],
                    "parallelGroup": 1,
                    "order": 1,
                },
                {
                    "tempId": "step_2",
                    "title": "Generate report",
                    "description": "Build summary report",
                    "assignedAgent": "nanobot",
                    "blockedBy": ["step_1"],
                    "parallelGroup": 2,
                    "order": 2,
                },
            ]
        }
    )

    plan = _parse_plan_response(raw)

    assert isinstance(plan, ExecutionPlan)
    assert plan.generated_by == LEAD_AGENT_NAME
    assert len(plan.steps) == 2
    assert plan.steps[0].temp_id == "step_1"
    assert plan.steps[0].title == "Extract data"
    assert plan.steps[0].parallel_group == 1
    assert plan.steps[1].blocked_by == ["step_1"]
    assert plan.steps[1].order == 2


def test_blocked_by_references_are_validated_against_temp_ids() -> None:
    raw = json.dumps(
        {
            "steps": [
                {
                    "tempId": "step_1",
                    "title": "A",
                    "description": "A",
                    "assignedAgent": "nanobot",
                    "blockedBy": [],
                },
                {
                    "tempId": "step_2",
                    "title": "B",
                    "description": "B",
                    "assignedAgent": "nanobot",
                    "blockedBy": ["step_1", "step_99", "step_2"],
                },
            ]
        }
    )

    plan = _parse_plan_response(raw)

    assert plan.steps[1].blocked_by == ["step_1"]


def test_parallel_group_normalization_for_independent_and_dependent_steps() -> None:
    raw = json.dumps(
        {
            "steps": [
                {
                    "tempId": "step_1",
                    "title": "A",
                    "description": "A",
                    "assignedAgent": "nanobot",
                    "blockedBy": [],
                    "parallelGroup": 3,
                },
                {
                    "tempId": "step_2",
                    "title": "B",
                    "description": "B",
                    "assignedAgent": "nanobot",
                    "blockedBy": [],
                    "parallelGroup": 9,
                },
                {
                    "tempId": "step_3",
                    "title": "C",
                    "description": "C",
                    "assignedAgent": "nanobot",
                    "blockedBy": ["step_1", "step_2"],
                    "parallelGroup": 1,
                },
            ]
        }
    )

    plan = _parse_plan_response(raw)

    assert plan.steps[0].parallel_group == plan.steps[1].parallel_group
    assert plan.steps[2].parallel_group > plan.steps[0].parallel_group


def test_missing_order_is_auto_assigned_sequentially() -> None:
    raw = json.dumps(
        {
            "steps": [
                {
                    "tempId": "step_1",
                    "title": "A",
                    "description": "A",
                    "assignedAgent": "nanobot",
                },
                {
                    "tempId": "step_2",
                    "title": "B",
                    "description": "B",
                    "assignedAgent": "nanobot",
                },
            ]
        }
    )

    plan = _parse_plan_response(raw)
    assert [s.order for s in plan.steps] == [1, 2]


def test_invalid_agent_names_fall_back_to_nanobot() -> None:
    planner = TaskPlanner()
    plan = ExecutionPlan(
        steps=[
            ExecutionPlanStep(
                temp_id="step_1",
                title="Do something",
                description="...",
                assigned_agent="nonexistent-agent",
            )
        ]
    )

    planner._validate_agent_names(plan, [_agent("finance-agent", ["finance"])])

    assert plan.steps[0].assigned_agent == NANOBOT_AGENT_NAME


def test_lead_agent_is_never_assigned_as_step_executor() -> None:
    planner = TaskPlanner()
    plan = ExecutionPlan(
        steps=[
            ExecutionPlanStep(
                temp_id="step_1",
                title="Do something",
                description="...",
                assigned_agent=LEAD_AGENT_NAME,
            )
        ]
    )

    planner._validate_agent_names(plan, [_agent(LEAD_AGENT_NAME, ["planning"])])

    assert plan.steps[0].assigned_agent == NANOBOT_AGENT_NAME


def test_system_agent_is_never_assigned_as_step_executor() -> None:
    """System agents (like low-agent) are for internal use only and must not execute task steps."""
    planner = TaskPlanner()
    system_agent = AgentData(
        name="low-agent",
        display_name="Low Agent",
        role="Lightweight system utility agent",
        skills=[],
        is_system=True,
    )
    plan = ExecutionPlan(
        steps=[
            ExecutionPlanStep(
                temp_id="step_1",
                title="Configure cron job",
                description="...",
                assigned_agent="low-agent",
            )
        ]
    )

    planner._validate_agent_names(plan, [system_agent, _agent("youtube-summarizer", ["youtube"])])

    assert plan.steps[0].assigned_agent == NANOBOT_AGENT_NAME


def test_system_agents_excluded_from_planner_roster() -> None:
    """System agents must not appear in the agent roster shown to the planner LLM."""
    from nanobot.mc.planner import _build_agent_roster

    agents = [
        _agent("youtube-summarizer", ["youtube"]),
        AgentData(
            name="low-agent",
            display_name="Low Agent",
            role="Lightweight system utility agent",
            skills=[],
            is_system=True,
        ),
        _agent("nanobot", ["general"]),
    ]

    roster = _build_agent_roster(agents)
    assert "low-agent" not in roster
    assert "youtube-summarizer" in roster
    assert "nanobot" in roster


def test_single_step_task_produces_valid_fallback_execution_plan() -> None:
    planner = TaskPlanner()

    plan = planner._fallback_heuristic_plan(
        "remind me to call the dentist", None, [], None
    )

    assert len(plan.steps) == 1
    assert plan.steps[0].temp_id == "step_1"
    assert plan.steps[0].title == "remind me to call the dentist"
    assert plan.steps[0].assigned_agent == NANOBOT_AGENT_NAME
    assert plan.steps[0].parallel_group == 1
    assert plan.steps[0].order == 1
    assert plan.generated_by == LEAD_AGENT_NAME


def test_execution_plan_to_dict_uses_camel_case_generated_fields() -> None:
    plan = ExecutionPlan(
        steps=[
            ExecutionPlanStep(
                temp_id="step_1",
                title="Extract data",
                description="Extract invoice data",
                assigned_agent="finance-agent",
                blocked_by=[],
                parallel_group=1,
                order=1,
            ),
            ExecutionPlanStep(
                temp_id="step_2",
                title="Generate report",
                description="Build summary report",
                assigned_agent=NANOBOT_AGENT_NAME,
                blocked_by=["step_1"],
                parallel_group=2,
                order=2,
            ),
        ]
    )

    payload = plan.to_dict()

    assert payload["steps"][0]["tempId"] == "step_1"
    assert payload["steps"][0]["title"] == "Extract data"
    assert payload["steps"][1]["blockedBy"] == ["step_1"]
    assert payload["generatedBy"] == LEAD_AGENT_NAME
    assert "generatedAt" in payload
    assert "createdAt" not in payload
    assert "stepId" not in payload["steps"][0]
    assert "dependsOn" not in payload["steps"][0]


# ---------------------------------------------------------------------------
# Story 6.3: _build_file_summary() tests (FR-F28, FR-F29)
# ---------------------------------------------------------------------------


def test_build_file_summary_with_files_returns_formatted_string() -> None:
    """_build_file_summary returns a formatted string with names, types, and sizes."""
    files = [
        {"name": "invoice.pdf", "type": "application/pdf", "size": 867328},
        {"name": "notes.md", "type": "text/markdown", "size": 12288},
    ]
    result = _build_file_summary(files)

    assert "2 attached file(s)" in result
    assert "invoice.pdf" in result
    assert "application/pdf" in result
    assert "notes.md" in result
    assert "text/markdown" in result
    assert "847 KB" in result   # 867328 // 1024 = 847
    assert "12 KB" in result    # 12288 // 1024 = 12
    assert "Consider file types" in result


def test_build_file_summary_with_empty_files_returns_empty_string() -> None:
    """_build_file_summary returns empty string for empty file list (AC #3)."""
    assert _build_file_summary([]) == ""


def test_build_file_summary_single_file() -> None:
    """_build_file_summary handles a single file correctly."""
    files = [
        {"name": "report.docx", "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "size": 51200},
    ]
    result = _build_file_summary(files)

    assert "1 attached file(s)" in result
    assert "report.docx" in result
    assert "50 KB" in result   # 51200 // 1024 = 50
    assert "Consider file types" in result


def test_build_file_summary_large_files_uses_mb_format() -> None:
    """_build_file_summary uses MB format for files >= 1 MB."""
    files = [
        {"name": "video.mp4", "type": "video/mp4", "size": 1073741824},  # 1 GB
        {"name": "data.csv", "type": "text/csv", "size": 2097152},        # 2 MB
    ]
    result = _build_file_summary(files)

    assert "video.mp4" in result
    assert "data.csv" in result
    # 1073741824 / 1048576 = 1024.0 MB
    assert "1024.0 MB" in result
    # 2097152 / 1048576 = 2.0 MB
    assert "2.0 MB" in result
    # Total: 1073741824 + 2097152 = 1075838976 bytes / 1048576 = 1026.0 MB
    assert "1026.0 MB" in result


def test_build_file_summary_zero_byte_file() -> None:
    """_build_file_summary handles zero-byte files gracefully."""
    files = [
        {"name": "empty.txt", "type": "text/plain", "size": 0},
    ]
    result = _build_file_summary(files)

    assert "1 attached file(s)" in result
    assert "empty.txt" in result
    assert "0 KB" in result


def test_build_file_summary_missing_type_defaults_to_octet_stream() -> None:
    """_build_file_summary defaults to application/octet-stream when type field is absent."""
    files = [
        {"name": "mystery.bin", "size": 1024},
    ]
    result = _build_file_summary(files)

    assert "mystery.bin" in result
    assert "application/octet-stream" in result


@pytest.mark.asyncio
async def test_llm_plan_includes_file_summary_in_prompt_when_files_present() -> None:
    """_llm_plan appends file summary to the user prompt when files are provided."""
    planner = TaskPlanner()
    agents = [_agent("nanobot", ["general"])]
    files = [
        {"name": "invoice.pdf", "type": "application/pdf", "size": 867328},
    ]

    captured_messages: list[list[dict]] = []

    def _fake_chat(**kwargs):
        captured_messages.append(kwargs["messages"])
        return json.dumps({
            "steps": [
                {
                    "tempId": "step_1",
                    "title": "Process invoice",
                    "description": "Process the invoice",
                    "assignedAgent": "nanobot",
                    "blockedBy": [],
                    "parallelGroup": 1,
                    "order": 1,
                }
            ]
        })

    fake_provider = type("FakeProvider", (), {"chat": staticmethod(_fake_chat)})()

    with patch("nanobot.mc.provider_factory.create_provider", return_value=(fake_provider, "fake-model")):
        await planner._llm_plan("Process invoice", "Analyze the attached invoice", agents, files=files)

    assert len(captured_messages) == 1
    user_prompt = captured_messages[0][1]["content"]
    assert "invoice.pdf" in user_prompt
    assert "application/pdf" in user_prompt
    assert "Consider file types" in user_prompt


@pytest.mark.asyncio
async def test_llm_plan_excludes_file_summary_when_no_files() -> None:
    """_llm_plan does NOT append file summary when files is empty or None (AC #3)."""
    planner = TaskPlanner()
    agents = [_agent("nanobot", ["general"])]

    captured_messages: list[list[dict]] = []

    def _fake_chat(**kwargs):
        captured_messages.append(kwargs["messages"])
        return json.dumps({
            "steps": [
                {
                    "tempId": "step_1",
                    "title": "Write report",
                    "description": "Write the report",
                    "assignedAgent": "nanobot",
                    "blockedBy": [],
                    "parallelGroup": 1,
                    "order": 1,
                }
            ]
        })

    fake_provider = type("FakeProvider", (), {"chat": staticmethod(_fake_chat)})()

    for files_arg in [[], None]:
        captured_messages.clear()
        with patch("nanobot.mc.provider_factory.create_provider", return_value=(fake_provider, "fake-model")):
            await planner._llm_plan("Write report", "Write a status report", agents, files=files_arg)

        assert len(captured_messages) == 1
        user_prompt = captured_messages[0][1]["content"]
        assert "Consider file types" not in user_prompt
        assert "attached file" not in user_prompt
