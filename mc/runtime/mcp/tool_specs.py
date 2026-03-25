"""Canonical MC MCP tool surface definitions.

Infrastructure tools (ask_user, send_message, etc.) are defined inline.
Entity tools (agent, skill, squad, workflow, review spec) are generated
from the shared specs in ``shared/specs/`` — the single source of truth
for field definitions across Python, TypeScript, and Convex.
"""

from __future__ import annotations

from mcp.types import Tool

from mc.runtime.mcp.entity_schemas import generate_all_tools

# ---------------------------------------------------------------------------
# Canonical tool specifications
# ---------------------------------------------------------------------------

MC_TOOLS: list[Tool] = [
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
    # -----------------------------------------------------------------
    # Entity tools — generated from shared/specs/ (single source of truth)
    # -----------------------------------------------------------------
    *generate_all_tools(),
    # -----------------------------------------------------------------
    # Infrastructure tools (continued)
    # -----------------------------------------------------------------
    Tool(
        name="search_memory",
        description=(
            "Search agent memory and history for relevant past events, decisions, "
            "and facts. Uses hybrid BM25 keyword + optional vector search."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — keywords or natural language question.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5).",
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["query"],
        },
    ),
]

# Backward-compatibility alias — existing code may import PHASE1_TOOLS.
PHASE1_TOOLS = MC_TOOLS
