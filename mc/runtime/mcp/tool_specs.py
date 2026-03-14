"""Canonical Phase 1 MC tool surface definitions.

This module is the single source of truth for the Phase 1 MCP tool schemas
used by MC nanobot execution.  Names are semantic and transport-agnostic;
namespace identity is carried by the MCP server identity, not by suffixes.

Phase 1 tools:
  ask_user, ask_agent, delegate_task, send_message, cron,
  report_progress, record_final_result
"""

from __future__ import annotations

from mcp.types import Tool

# ---------------------------------------------------------------------------
# Phase 1 canonical tool specifications
# ---------------------------------------------------------------------------

PHASE1_TOOLS: list[Tool] = [
    Tool(
        name="ask_user",
        description=(
            "Ask the user one question or a short structured questionnaire and wait for "
            "their reply. Use for clarifications, decisions, approvals, and multi-step "
            "intake. For structured questionnaires, provide up to 3 questions, each with "
            "up to 3 options; the UI always allows a fourth free-text response."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "A single question to ask the user.",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 3,
                    "description": (
                        "Optional answer choices for a single question. Provide up to 3; "
                        "the UI always allows a fourth free-text response."
                    ),
                },
                "questions": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "description": (
                        "Structured questionnaire with up to 3 questions. Use this when "
                        "you need multiple answers in one interaction."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "header": {
                                "type": "string",
                                "description": "Short label shown before the question.",
                            },
                            "id": {
                                "type": "string",
                                "description": "Stable identifier for the answer.",
                            },
                            "question": {
                                "type": "string",
                                "description": "Question shown to the user.",
                            },
                            "options": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 3,
                                "description": (
                                    "Suggested choices. Provide up to 3; the UI always "
                                    "allows a fourth free-text response."
                                ),
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {
                                            "type": "string",
                                            "description": "Short user-facing option label.",
                                        },
                                        "description": {
                                            "type": "string",
                                            "description": "One-sentence description or tradeoff.",
                                        },
                                    },
                                    "required": ["label", "description"],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": ["header", "id", "question", "options"],
                        "additionalProperties": False,
                    },
                },
            },
            "oneOf": [
                {"required": ["question"]},
                {"required": ["questions"]},
            ],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="ask_agent",
        description=(
            "Ask another agent a question and wait for their response. "
            "Use for clarification or specialist opinion. Depth limit: 2."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "Name of the agent to ask."},
                "question": {"type": "string", "description": "The question to ask."},
            },
            "required": ["agent_name", "question"],
        },
    ),
    Tool(
        name="delegate_task",
        description=(
            "Delegate a task to Mission Control. Creates an async task assigned to another agent."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "What needs to be done."},
                "agent": {
                    "type": "string",
                    "description": "Agent to assign the task to (optional).",
                },
                "priority": {
                    "type": "string",
                    "description": "Task priority: low/medium/high (optional).",
                },
            },
            "required": ["description"],
        },
    ),
    Tool(
        name="send_message",
        description=(
            "Send a message to the user or a channel. "
            "Use to proactively communicate progress or results."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Message body."},
                "channel": {"type": "string", "description": "Target channel (optional)."},
                "chat_id": {"type": "string", "description": "Target chat/user ID (optional)."},
                "media": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional list of file paths to attach (images, audio, documents)."
                    ),
                },
            },
            "required": ["content"],
        },
    ),
    Tool(
        name="cron",
        description="Schedule reminders and recurring tasks. Actions: add, list, remove.",
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove"],
                    "description": "Action to perform.",
                },
                "message": {
                    "type": "string",
                    "description": "Reminder message (required for add).",
                },
                "every_seconds": {
                    "type": "integer",
                    "description": "Interval in seconds (for recurring tasks).",
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression like '0 9 * * *'.",
                },
                "tz": {
                    "type": "string",
                    "description": "IANA timezone for cron expressions.",
                },
                "at": {
                    "type": "string",
                    "description": "ISO datetime for one-time execution.",
                },
                "job_id": {
                    "type": "string",
                    "description": "Job ID (required for remove).",
                },
            },
            "required": ["action"],
        },
    ),
    Tool(
        name="report_progress",
        description="Report task progress to Mission Control.",
        inputSchema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Progress description."},
                "percentage": {
                    "type": "integer",
                    "description": "Completion percentage 0-100 (optional).",
                    "minimum": 0,
                    "maximum": 100,
                },
            },
            "required": ["message"],
        },
    ),
    Tool(
        name="record_final_result",
        description=(
            "Record the canonical final result for a backend-owned Mission Control step. "
            "Use exactly once when the step is complete, before ending the turn."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": ("Final answer text to post to the task thread on completion."),
                }
            },
            "required": ["content"],
            "additionalProperties": False,
        },
    ),
]
