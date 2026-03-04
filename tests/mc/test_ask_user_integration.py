"""Integration test: registry is populated during CC task execution."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from mc.ask_user_registry import AskUserRegistry


class TestRegistryWiring:
    def test_step_dispatcher_accepts_registry(self):
        """StepDispatcher.__init__ accepts and stores ask_user_registry."""
        from mc.step_dispatcher import StepDispatcher

        registry = AskUserRegistry()
        bridge = MagicMock()
        dispatcher = StepDispatcher(bridge, ask_user_registry=registry)
        assert dispatcher._ask_user_registry is registry

    def test_step_dispatcher_default_none(self):
        """StepDispatcher defaults ask_user_registry to None."""
        from mc.step_dispatcher import StepDispatcher

        bridge = MagicMock()
        dispatcher = StepDispatcher(bridge)
        assert dispatcher._ask_user_registry is None

    def test_executor_accepts_registry(self):
        """TaskExecutor.__init__ accepts and stores ask_user_registry."""
        from mc.executor import TaskExecutor

        registry = AskUserRegistry()
        bridge = MagicMock()
        executor = TaskExecutor(bridge, ask_user_registry=registry)
        assert executor._ask_user_registry is registry

    def test_executor_default_none(self):
        """TaskExecutor defaults ask_user_registry to None."""
        from mc.executor import TaskExecutor

        bridge = MagicMock()
        executor = TaskExecutor(bridge)
        assert executor._ask_user_registry is None
