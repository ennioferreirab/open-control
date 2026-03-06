"""
nanobot Mission Control — Multi-agent orchestration platform.

This package provides the Python-side components for Mission Control:
- bridge: ConvexBridge for Convex backend communication
- types: Shared Python types mirroring the Convex schema
- gateway: Agent Gateway (Story 1.5+)
- orchestrator: Lead Agent routing (Story 4.1+)
- state_machine: Task state transitions (Story 2.4+)
- yaml_validator: Agent YAML validation (Story 3.1+)
- process_manager: Subprocess management (Story 1.5+)
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
