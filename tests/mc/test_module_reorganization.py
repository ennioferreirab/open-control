from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_context_packages_reexport_public_api() -> None:
    from mc.contexts.agents.sync import AgentSyncService as ContextAgentSyncService
    from mc.contexts.conversation import (
        ChatHandler,
        ConversationIntent,
        ConversationService,
    )
    from mc.contexts.conversation.chat_handler import (
        ChatHandler as ContextChatHandler,
    )
    from mc.contexts.conversation.intent import (
        ConversationIntent as ContextConversationIntent,
    )
    from mc.contexts.conversation.service import (
        ConversationService as ContextConversationService,
    )
    from mc.contexts.execution import (
        CCExecutorMixin,
        StepDispatcher,
        TaskExecutor,
        execute_step_via_cc,
    )
    from mc.contexts.execution.cc_executor import (
        CCExecutorMixin as ContextCCExecutorMixin,
    )
    from mc.contexts.execution.cc_step_runner import (
        execute_step_via_cc as ContextExecuteStepViaCc,
    )
    from mc.contexts.execution.executor import TaskExecutor as ContextTaskExecutor
    from mc.contexts.execution.step_dispatcher import (
        StepDispatcher as ContextStepDispatcher,
    )
    from mc.contexts.planning import (
        PlanMaterializer,
        TaskPlanner,
        generate_title_via_low_agent,
        handle_plan_negotiation,
        start_plan_negotiation_loop,
    )
    from mc.contexts.planning.materializer import (
        PlanMaterializer as ContextPlanMaterializer,
    )
    from mc.contexts.planning.negotiation import (
        handle_plan_negotiation as ContextHandlePlanNegotiation,
    )
    from mc.contexts.planning.negotiation import (
        start_plan_negotiation_loop as ContextStartPlanNegotiationLoop,
    )
    from mc.contexts.planning.planner import TaskPlanner as ContextTaskPlanner
    from mc.contexts.planning.title_generation import (
        generate_title_via_low_agent as ContextGenerateTitle,
    )
    from mc.contexts.review import ReviewHandler
    from mc.contexts.review.handler import ReviewHandler as ContextReviewHandler
    from mc.runtime import (
        TaskOrchestrator,
        generate_title_via_low_agent as RuntimeGenerateTitle,
        main,
        run_gateway,
    )
    from mc.runtime.gateway import main as RuntimeMain
    from mc.runtime.gateway import run_gateway as RuntimeRunGateway
    from mc.runtime.orchestrator import TaskOrchestrator as RuntimeTaskOrchestrator
    from mc.services.agent_sync import AgentSyncService
    from mc.services.conversation import ConversationService as ServiceConversation
    from mc.services.conversation_intent import (
        ConversationIntent as ServiceConversationIntent,
    )

    assert TaskOrchestrator is RuntimeTaskOrchestrator
    assert main is RuntimeMain
    assert run_gateway is RuntimeRunGateway
    assert RuntimeGenerateTitle is ContextGenerateTitle
    assert TaskPlanner is ContextTaskPlanner
    assert PlanMaterializer is ContextPlanMaterializer
    assert handle_plan_negotiation is ContextHandlePlanNegotiation
    assert start_plan_negotiation_loop is ContextStartPlanNegotiationLoop
    assert TaskExecutor is ContextTaskExecutor
    assert StepDispatcher is ContextStepDispatcher
    assert CCExecutorMixin is ContextCCExecutorMixin
    assert execute_step_via_cc is ContextExecuteStepViaCc
    assert ChatHandler is ContextChatHandler
    assert ConversationService is ContextConversationService
    assert ConversationIntent is ContextConversationIntent
    assert ReviewHandler is ContextReviewHandler
    assert AgentSyncService is ContextAgentSyncService
    assert ServiceConversation is ContextConversationService
    assert ServiceConversationIntent is ContextConversationIntent


def test_runtime_workers_package_reexports_existing_workers() -> None:
    from mc.runtime.workers import (
        InboxWorker,
        KickoffResumeWorker,
        PlanningWorker,
        ReviewWorker,
    )
    from mc.workers import (
        InboxWorker as LegacyInboxWorker,
        KickoffResumeWorker as LegacyKickoffResumeWorker,
        PlanningWorker as LegacyPlanningWorker,
        ReviewWorker as LegacyReviewWorker,
    )

    assert InboxWorker is LegacyInboxWorker
    assert PlanningWorker is LegacyPlanningWorker
    assert ReviewWorker is LegacyReviewWorker
    assert KickoffResumeWorker is LegacyKickoffResumeWorker


@pytest.mark.parametrize(
    "module_name",
    [
        "mc.gateway",
        "mc.orchestrator",
        "mc.planner",
        "mc.plan_materializer",
        "mc.plan_negotiator",
        "mc.executor",
        "mc.cc_executor",
        "mc.cc_step_runner",
        "mc.step_dispatcher",
        "mc.chat_handler",
        "mc.review_handler",
    ],
)
def test_removed_root_facades_are_not_importable(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


def test_mc_root_contains_only_package_and_types() -> None:
    root = Path(__file__).resolve().parents[2] / "mc"
    root_modules = sorted(p.name for p in root.glob("*.py") if p.is_file())
    assert root_modules == ["__init__.py", "types.py"]
