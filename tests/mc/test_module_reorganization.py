from __future__ import annotations

from pathlib import Path


def test_public_facades_delegate_to_runtime_and_contexts() -> None:
    from mc.chat_handler import ChatHandler
    from mc.contexts.agents.sync import AgentSyncService as ContextAgentSyncService
    from mc.contexts.conversation.chat_handler import (
        ChatHandler as ContextChatHandler,
    )
    from mc.contexts.conversation.intent import (
        ConversationIntent as ContextConversationIntent,
    )
    from mc.contexts.conversation.service import (
        ConversationService as ContextConversationService,
    )
    from mc.contexts.execution.cc_executor import (
        CCExecutorMixin as ContextCCExecutorMixin,
    )
    from mc.contexts.execution.cc_step_runner import (
        execute_step_via_cc as context_execute_step_via_cc,
    )
    from mc.contexts.execution.executor import TaskExecutor as ContextTaskExecutor
    from mc.contexts.execution.step_dispatcher import (
        StepDispatcher as ContextStepDispatcher,
    )
    from mc.contexts.planning.materializer import (
        PlanMaterializer as ContextPlanMaterializer,
    )
    from mc.contexts.planning.negotiation import (
        handle_plan_negotiation as context_handle_plan_negotiation,
    )
    from mc.contexts.planning.negotiation import (
        start_plan_negotiation_loop as context_start_plan_negotiation_loop,
    )
    from mc.contexts.planning.planner import TaskPlanner as ContextTaskPlanner
    from mc.contexts.planning.title_generation import (
        generate_title_via_low_agent as context_generate_title,
    )
    from mc.contexts.review.handler import ReviewHandler as ContextReviewHandler
    from mc.executor import TaskExecutor
    from mc.gateway import main, run_gateway
    from mc.orchestrator import TaskOrchestrator, generate_title_via_low_agent
    from mc.plan_materializer import PlanMaterializer
    from mc.plan_negotiator import (
        handle_plan_negotiation,
        start_plan_negotiation_loop,
    )
    from mc.planner import TaskPlanner
    from mc.review_handler import ReviewHandler
    from mc.runtime.gateway import main as runtime_main
    from mc.runtime.gateway import run_gateway as runtime_run_gateway
    from mc.runtime.orchestrator import TaskOrchestrator as RuntimeTaskOrchestrator
    from mc.runtime.orchestrator import (
        generate_title_via_low_agent as runtime_generate_title,
    )
    from mc.services.agent_sync import AgentSyncService
    from mc.services.conversation import ConversationService
    from mc.services.conversation_intent import ConversationIntent
    from mc.step_dispatcher import StepDispatcher

    assert TaskOrchestrator is RuntimeTaskOrchestrator
    assert generate_title_via_low_agent is runtime_generate_title
    assert generate_title_via_low_agent is context_generate_title
    assert main is runtime_main
    assert run_gateway is runtime_run_gateway
    assert TaskPlanner is ContextTaskPlanner
    assert PlanMaterializer is ContextPlanMaterializer
    assert handle_plan_negotiation is context_handle_plan_negotiation
    assert start_plan_negotiation_loop is context_start_plan_negotiation_loop
    assert TaskExecutor is ContextTaskExecutor
    assert StepDispatcher is ContextStepDispatcher
    assert ChatHandler is ContextChatHandler
    assert ReviewHandler is ContextReviewHandler
    assert ConversationService is ContextConversationService
    assert ConversationIntent is ContextConversationIntent
    assert AgentSyncService is ContextAgentSyncService

    from mc.cc_executor import CCExecutorMixin
    from mc.cc_step_runner import execute_step_via_cc

    assert CCExecutorMixin is ContextCCExecutorMixin
    assert execute_step_via_cc is context_execute_step_via_cc


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


def test_facade_modules_are_thin_reexports() -> None:
    root = Path(__file__).resolve().parents[2]
    expected_imports = {
        "mc/gateway.py": "mc.runtime.gateway",
        "mc/orchestrator.py": "mc.runtime.orchestrator",
        "mc/planner.py": "mc.contexts.planning.planner",
        "mc/plan_materializer.py": "mc.contexts.planning.materializer",
        "mc/plan_negotiator.py": "mc.contexts.planning.negotiation",
        "mc/executor.py": "mc.contexts.execution.executor",
        "mc/cc_executor.py": "mc.contexts.execution.cc_executor",
        "mc/cc_step_runner.py": "mc.contexts.execution.cc_step_runner",
        "mc/step_dispatcher.py": "mc.contexts.execution.step_dispatcher",
        "mc/chat_handler.py": "mc.contexts.conversation.chat_handler",
        "mc/review_handler.py": "mc.contexts.review.handler",
        "mc/services/conversation.py": "mc.contexts.conversation.service",
        "mc/services/conversation_intent.py": "mc.contexts.conversation.intent",
        "mc/services/agent_sync.py": "mc.contexts.agents.sync",
    }

    for relative_path, import_path in expected_imports.items():
        content = (root / relative_path).read_text(encoding="utf-8")
        assert import_path in content, (
            f"{relative_path} should be a thin facade importing from {import_path}"
        )
