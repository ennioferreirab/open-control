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
        execute_step_via_cc as context_execute_step_via_cc,
    )
    from mc.contexts.execution.executor import TaskExecutor as ContextTaskExecutor
    from mc.contexts.execution.step_dispatcher import (
        StepDispatcher as ContextStepDispatcher,
    )
    from mc.contexts.planning import (
        PlanMaterializer,
        TaskPlanner,
        handle_plan_negotiation,
        start_plan_negotiation_loop,
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
    from mc.contexts.review import ReviewHandler
    from mc.contexts.review.handler import ReviewHandler as ContextReviewHandler
    from mc.runtime import (
        TaskOrchestrator,
        main,
        run_gateway,
    )
    from mc.runtime import (
        generate_title_via_low_agent as runtime_generate_title,
    )
    from mc.runtime.gateway import main as runtime_main
    from mc.runtime.gateway import run_gateway as runtime_run_gateway
    from mc.runtime.orchestrator import TaskOrchestrator as RuntimeTaskOrchestrator

    assert TaskOrchestrator is RuntimeTaskOrchestrator
    assert main is runtime_main
    assert run_gateway is runtime_run_gateway
    assert runtime_generate_title is context_generate_title
    assert TaskPlanner is ContextTaskPlanner
    assert PlanMaterializer is ContextPlanMaterializer
    assert handle_plan_negotiation is context_handle_plan_negotiation
    assert start_plan_negotiation_loop is context_start_plan_negotiation_loop
    assert TaskExecutor is ContextTaskExecutor
    assert StepDispatcher is ContextStepDispatcher
    assert CCExecutorMixin is ContextCCExecutorMixin
    assert execute_step_via_cc is context_execute_step_via_cc
    assert ChatHandler is ContextChatHandler
    assert ConversationService is ContextConversationService
    assert ConversationIntent is ContextConversationIntent
    assert ReviewHandler is ContextReviewHandler
    assert ContextAgentSyncService is not None


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
        "mc.ask_user",
        "mc.mentions",
        "mc.review_handler",
        "mc.services",
        "mc.workers",
    ],
)
def test_removed_root_facades_are_not_importable(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


def test_mc_root_contains_only_package_and_types() -> None:
    root = Path(__file__).resolve().parents[2] / "mc"
    root_modules = sorted(p.name for p in root.glob("*.py") if p.is_file())
    assert root_modules == ["__init__.py", "types.py"]
