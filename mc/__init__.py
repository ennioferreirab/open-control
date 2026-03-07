"""
nanobot Mission Control — Multi-agent orchestration platform.

This package provides the Python-side components for Mission Control:
- bridge: ConvexBridge for Convex backend communication
- types: Shared Python types mirroring the Convex schema
- runtime: composition roots and long-running loops
- contexts: planning, execution, conversation, review, and agent sync
- infrastructure: config, providers, bootstrap, and filesystem helpers
- domain: workflow and invariant helpers
- root package: only `__init__` and `types`
"""

from mc.bridge import ConvexBridge
from mc.types import (
    LEAD_AGENT_NAME,
    NANOBOT_AGENT_NAME,
    AgentData,
    AgentStatus,
    ArtifactData,
    ExecutionPlan,
    ExecutionPlanStep,
    MessageData,
    MessageType,
    StepStatus,
    TaskData,
    TaskStatus,
    ThreadMessageType,
    TrustLevel,
)

__all__ = [
    # Core
    "ConvexBridge",
    # Enums
    "TaskStatus",
    "StepStatus",
    "TrustLevel",
    "AgentStatus",
    "MessageType",
    "ThreadMessageType",
    # Data classes
    "TaskData",
    "AgentData",
    "ArtifactData",
    "MessageData",
    "ExecutionPlan",
    "ExecutionPlanStep",
    # Constants
    "LEAD_AGENT_NAME",
    "NANOBOT_AGENT_NAME",
    # Sub-packages
    "memory",
]
