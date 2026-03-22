"""Canonical MC MCP tool surface definitions.

This module is the single source of truth for the MCP tool schemas
used by MC nanobot execution.  Names are semantic and transport-agnostic;
namespace identity is carried by the MCP server identity, not by suffixes.
"""

from __future__ import annotations

from mcp.types import Tool

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
    Tool(
        name="create_agent_spec",
        description=(
            "Create a V2 agent specification in Mission Control. "
            "Defines the agent's identity, responsibilities, principles, and policies."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Agent name slug (unique identifier).",
                },
                "displayName": {
                    "type": "string",
                    "description": "Human-readable display name for the agent.",
                },
                "role": {
                    "type": "string",
                    "description": "Agent role description.",
                },
                "responsibilities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "What this agent is responsible for.",
                },
                "nonGoals": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "What this agent explicitly does NOT do.",
                },
                "principles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Core principles guiding the agent.",
                },
                "workingStyle": {
                    "type": "string",
                    "description": "Description of how the agent approaches tasks.",
                },
                "qualityRules": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Rules for producing quality output.",
                },
                "antiPatterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Patterns this agent explicitly avoids.",
                },
                "outputContract": {
                    "type": "string",
                    "description": "Description of outputs this agent produces.",
                },
                "toolPolicy": {
                    "type": "string",
                    "description": "Policy for tool usage.",
                },
                "memoryPolicy": {
                    "type": "string",
                    "description": "Policy for memory and context persistence.",
                },
                "executionPolicy": {
                    "type": "string",
                    "description": "Policy for task execution.",
                },
                "reviewPolicyRef": {
                    "type": "string",
                    "description": "Reference to a review policy.",
                },
                "skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of skill names the agent uses.",
                },
                "model": {
                    "type": "string",
                    "description": "Optional model identifier override.",
                },
            },
            "required": ["name", "displayName", "role"],
            "additionalProperties": False,
        },
    ),
    Tool(
        name="publish_squad_graph",
        description=(
            "Publish a complete squad blueprint to Mission Control. "
            "Creates the squad, its agents, and workflows in a single operation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "squad": {
                    "type": "object",
                    "description": "Squad identity and metadata.",
                    "properties": {
                        "name": {"type": "string", "description": "Squad name slug."},
                        "displayName": {
                            "type": "string",
                            "description": "Human-readable squad name.",
                        },
                        "description": {
                            "type": "string",
                            "description": "Optional squad description.",
                        },
                        "outcome": {
                            "type": "string",
                            "description": "Optional desired outcome statement.",
                        },
                    },
                    "required": ["name", "displayName"],
                    "additionalProperties": False,
                },
                "agents": {
                    "type": "array",
                    "description": "Agent entries in the squad.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "Local key used in workflow steps.",
                            },
                            "name": {"type": "string", "description": "Agent name slug."},
                            "role": {"type": "string", "description": "Agent role."},
                            "displayName": {
                                "type": "string",
                                "description": "Optional human-readable name.",
                            },
                        },
                        "required": ["key", "name", "role"],
                        "additionalProperties": False,
                    },
                },
                "workflows": {
                    "type": "array",
                    "description": "Workflow definitions for the squad.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "Workflow key."},
                            "name": {"type": "string", "description": "Workflow name."},
                            "steps": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "key": {
                                            "type": "string",
                                            "description": "Step key.",
                                        },
                                        "type": {
                                            "type": "string",
                                            "enum": [
                                                "agent",
                                                "human",
                                                "checkpoint",
                                                "review",
                                                "system",
                                            ],
                                            "description": "Step type.",
                                        },
                                        "agentKey": {
                                            "type": "string",
                                            "description": "Agent key for this step.",
                                        },
                                        "dependsOn": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "Step keys this step depends on.",
                                        },
                                        "title": {
                                            "type": "string",
                                            "description": "Optional step title.",
                                        },
                                        "description": {
                                            "type": "string",
                                            "description": "Optional step description.",
                                        },
                                    },
                                    "required": ["key", "type"],
                                    "additionalProperties": False,
                                },
                            },
                            "exitCriteria": {
                                "type": "string",
                                "description": "Optional workflow exit criteria.",
                            },
                        },
                        "required": ["key", "name", "steps"],
                        "additionalProperties": False,
                    },
                },
                "reviewPolicy": {
                    "type": "string",
                    "description": "Optional review policy for the squad.",
                },
            },
            "required": ["squad", "agents", "workflows"],
            "additionalProperties": False,
        },
    ),
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
