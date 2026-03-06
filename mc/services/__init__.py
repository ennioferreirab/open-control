"""Service layer — extracted from gateway.py for modular runtime supervision.

Story 17.2: Process Monitor, Sync and Crash Services.
Story 17.3: Unified Conversation Services.

Exports:
    AgentSyncService — agent, skills, settings, model-tier sync
    CrashRecoveryService — crash detection, retry policy, escalation
    PlanNegotiationSupervisor — per-task plan negotiation loop management
    ConversationIntentResolver — classifies thread messages into intents
    ConversationService — unified message classification and routing
"""

from mc.services.agent_sync import AgentSyncService
from mc.services.conversation import ConversationService
from mc.services.conversation_intent import (
    ConversationIntent,
    ConversationIntentResolver,
)
from mc.services.crash_recovery import CrashRecoveryService
from mc.services.plan_negotiation import PlanNegotiationSupervisor

__all__ = [
    "AgentSyncService",
    "ConversationIntent",
    "ConversationIntentResolver",
    "ConversationService",
    "CrashRecoveryService",
    "PlanNegotiationSupervisor",
]
