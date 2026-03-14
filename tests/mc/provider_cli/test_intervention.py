"""Tests for HumanInterventionController."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mc.contexts.provider_cli.registry import ProviderSessionRegistry
from mc.contexts.provider_cli.types import ProviderProcessHandle, SessionStatus
from mc.runtime.provider_cli.intervention import HumanInterventionController


def _make_handle(mc_session_id: str = "s1") -> ProviderProcessHandle:
    return ProviderProcessHandle(
        mc_session_id=mc_session_id,
        provider="test-provider",
        pid=12345,
        pgid=12345,
        cwd="/tmp",
        command=["test-cmd"],
        started_at="2026-01-01T00:00:00+00:00",
    )


def _make_registry(
    mc_session_id: str = "s1",
    *,
    supports_resume: bool = True,
    supports_interrupt: bool = True,
    supports_stop: bool = True,
    initial_status: SessionStatus = SessionStatus.RUNNING,
) -> ProviderSessionRegistry:
    registry = ProviderSessionRegistry()
    registry.create(
        mc_session_id=mc_session_id,
        provider="test-provider",
        pid=12345,
        pgid=12345,
        mode="provider-native",
        supports_resume=supports_resume,
        supports_interrupt=supports_interrupt,
        supports_stop=supports_stop,
    )
    if initial_status != SessionStatus.STARTING:
        registry.update_status(mc_session_id, SessionStatus.RUNNING)
        if initial_status == SessionStatus.HUMAN_INTERVENING:
            registry.update_status(mc_session_id, SessionStatus.INTERRUPTING)
            registry.update_status(mc_session_id, SessionStatus.HUMAN_INTERVENING)
        elif initial_status != SessionStatus.RUNNING:
            registry.update_status(mc_session_id, initial_status)
    return registry


def _make_parser(
    *,
    resume_raises: Exception | None = None,
    interrupt_raises: Exception | None = None,
    stop_raises: Exception | None = None,
) -> MagicMock:
    parser = MagicMock()
    parser.provider_name = "test-provider"
    parser.interrupt = AsyncMock(side_effect=interrupt_raises)
    parser.resume = AsyncMock(side_effect=resume_raises)
    parser.stop = AsyncMock(side_effect=stop_raises)
    return parser


def _make_controller(
    registry: ProviderSessionRegistry | None = None,
) -> HumanInterventionController:
    if registry is None:
        registry = _make_registry()
    return HumanInterventionController(registry=registry)


class TestInterrupt:
    async def test_transitions_running_to_human_intervening(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.RUNNING)
        controller = _make_controller(registry=registry)
        await controller.interrupt("s1", _make_handle(), _make_parser())
        assert registry.require("s1").status == SessionStatus.HUMAN_INTERVENING

    async def test_calls_parser_interrupt_with_handle(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.RUNNING)
        handle = _make_handle()
        parser = _make_parser()
        controller = _make_controller(registry=registry)
        await controller.interrupt("s1", handle, parser)
        parser.interrupt.assert_awaited_once_with(handle)

    async def test_transitions_through_interrupting(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.RUNNING)
        handle = _make_handle()
        status_log: list[SessionStatus] = []
        parser = _make_parser()

        async def capture(h: ProviderProcessHandle) -> None:
            status_log.append(registry.require("s1").status)

        parser.interrupt = AsyncMock(side_effect=capture)
        controller = _make_controller(registry=registry)
        await controller.interrupt("s1", handle, parser)
        assert SessionStatus.INTERRUPTING in status_log
        assert registry.require("s1").status == SessionStatus.HUMAN_INTERVENING

    async def test_failure_transitions_to_crashed(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.RUNNING)
        parser = _make_parser(interrupt_raises=RuntimeError("signal failed"))
        controller = _make_controller(registry=registry)
        with pytest.raises(RuntimeError, match="signal failed"):
            await controller.interrupt("s1", _make_handle(), parser)
        assert registry.require("s1").status == SessionStatus.CRASHED

    async def test_from_invalid_state_raises(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.HUMAN_INTERVENING)
        controller = _make_controller(registry=registry)
        with pytest.raises(ValueError):
            await controller.interrupt("s1", _make_handle(), _make_parser())


class TestResume:
    async def test_transitions_human_intervening_to_running(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.HUMAN_INTERVENING)
        controller = _make_controller(registry=registry)
        await controller.resume("s1", _make_handle(), "continue", _make_parser())
        assert registry.require("s1").status == SessionStatus.RUNNING

    async def test_calls_parser_resume_with_message(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.HUMAN_INTERVENING)
        handle = _make_handle()
        parser = _make_parser()
        controller = _make_controller(registry=registry)
        await controller.resume("s1", handle, "my message", parser)
        parser.resume.assert_awaited_once_with(handle, "my message")

    async def test_transitions_through_resuming(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.HUMAN_INTERVENING)
        handle = _make_handle()
        status_log: list[SessionStatus] = []
        parser = _make_parser()

        async def capture(h: ProviderProcessHandle, msg: str) -> None:
            status_log.append(registry.require("s1").status)

        parser.resume = AsyncMock(side_effect=capture)
        controller = _make_controller(registry=registry)
        await controller.resume("s1", handle, "go", parser)
        assert SessionStatus.RESUMING in status_log
        assert registry.require("s1").status == SessionStatus.RUNNING

    async def test_raises_when_provider_does_not_support_it(self) -> None:
        registry = _make_registry(
            initial_status=SessionStatus.HUMAN_INTERVENING, supports_resume=False
        )
        parser = _make_parser(resume_raises=NotImplementedError("runtime-owned"))
        controller = _make_controller(registry=registry)
        with pytest.raises(NotImplementedError):
            await controller.resume("s1", _make_handle(), "hello", parser)
        assert registry.require("s1").status == SessionStatus.CRASHED

    async def test_failure_transitions_to_crashed(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.HUMAN_INTERVENING)
        parser = _make_parser(resume_raises=RuntimeError("write failed"))
        controller = _make_controller(registry=registry)
        with pytest.raises(RuntimeError, match="write failed"):
            await controller.resume("s1", _make_handle(), "hello", parser)
        assert registry.require("s1").status == SessionStatus.CRASHED

    async def test_from_invalid_state_raises(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.RUNNING)
        controller = _make_controller(registry=registry)
        with pytest.raises(ValueError):
            await controller.resume("s1", _make_handle(), "hello", _make_parser())


class TestStop:
    async def test_from_running_transitions_to_stopped(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.RUNNING)
        controller = _make_controller(registry=registry)
        await controller.stop("s1", _make_handle(), _make_parser())
        assert registry.require("s1").status == SessionStatus.STOPPED

    async def test_from_human_intervening_transitions_to_stopped(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.HUMAN_INTERVENING)
        controller = _make_controller(registry=registry)
        await controller.stop("s1", _make_handle(), _make_parser())
        assert registry.require("s1").status == SessionStatus.STOPPED

    async def test_calls_parser_stop(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.RUNNING)
        handle = _make_handle()
        parser = _make_parser()
        controller = _make_controller(registry=registry)
        await controller.stop("s1", handle, parser)
        parser.stop.assert_awaited_once_with(handle)

    async def test_from_interrupting_transitions_to_stopped(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.RUNNING)
        registry.update_status("s1", SessionStatus.INTERRUPTING)
        controller = _make_controller(registry=registry)
        await controller.stop("s1", _make_handle(), _make_parser())
        assert registry.require("s1").status == SessionStatus.STOPPED

    async def test_failure_transitions_to_crashed(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.RUNNING)
        parser = _make_parser(stop_raises=RuntimeError("process gone"))
        controller = _make_controller(registry=registry)
        with pytest.raises(RuntimeError, match="process gone"):
            await controller.stop("s1", _make_handle(), parser)
        assert registry.require("s1").status == SessionStatus.CRASHED


class TestGetInterventionState:
    def test_returns_current_status(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.RUNNING)
        controller = _make_controller(registry=registry)
        assert controller.get_intervention_state("s1") == SessionStatus.RUNNING

    def test_after_status_change(self) -> None:
        registry = _make_registry(initial_status=SessionStatus.RUNNING)
        registry.update_status("s1", SessionStatus.INTERRUPTING)
        controller = _make_controller(registry=registry)
        assert controller.get_intervention_state("s1") == SessionStatus.INTERRUPTING

    def test_raises_for_unknown_session(self) -> None:
        controller = _make_controller(registry=ProviderSessionRegistry())
        with pytest.raises(ValueError, match="not found"):
            controller.get_intervention_state("nonexistent")
