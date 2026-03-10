from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _mutation_payloads(bridge: MagicMock) -> list[dict]:
    return [
        json.loads(call.args[1]["value"])
        for call in bridge.mutation.call_args_list
        if call.args and call.args[0] == "settings:set"
    ]


@pytest.mark.asyncio
async def test_initialize_persists_active_runtime_state() -> None:
    from mc.runtime.sleep_controller import RuntimeSleepController

    bridge = MagicMock()
    controller = RuntimeSleepController(bridge, time_fn=_FakeClock())

    await controller.initialize()

    payload = _mutation_payloads(bridge)[-1]
    assert payload["mode"] == "active"
    assert payload["pollIntervalSeconds"] == 5
    assert payload["manualRequested"] is False
    assert payload["reason"] == "startup"


@pytest.mark.asyncio
async def test_auto_sleep_after_five_minutes_without_work() -> None:
    from mc.runtime.sleep_controller import RuntimeSleepController

    clock = _FakeClock()
    bridge = MagicMock()
    controller = RuntimeSleepController(bridge, time_fn=clock)

    await controller.initialize()
    clock.advance(300)
    await controller.record_idle()

    payload = _mutation_payloads(bridge)[-1]
    assert payload["mode"] == "sleep"
    assert payload["pollIntervalSeconds"] == 300
    assert payload["manualRequested"] is False
    assert payload["reason"] == "idle"


@pytest.mark.asyncio
async def test_work_found_wakes_sleep_and_clears_manual_override() -> None:
    from mc.runtime.sleep_controller import RuntimeSleepController

    bridge = MagicMock()
    controller = RuntimeSleepController(bridge, time_fn=_FakeClock())

    await controller.initialize()
    await controller.apply_manual_mode("sleep")
    await controller.record_work_found()

    payload = _mutation_payloads(bridge)[-1]
    assert payload["mode"] == "active"
    assert payload["pollIntervalSeconds"] == 5
    assert payload["manualRequested"] is False
    assert payload["reason"] == "work_found"


@pytest.mark.asyncio
async def test_manual_wake_interrupts_sleep_wait_immediately() -> None:
    from mc.runtime.sleep_controller import RuntimeSleepController

    bridge = MagicMock()
    controller = RuntimeSleepController(
        bridge,
        time_fn=_FakeClock(),
        sleep_poll_interval_seconds=300,
    )

    await controller.initialize()
    await controller.apply_manual_mode("sleep")

    waiter = asyncio.create_task(controller.wait_for_next_cycle(5))
    await asyncio.sleep(0)
    assert not waiter.done()

    await controller.apply_manual_mode("active")
    await asyncio.wait_for(waiter, timeout=1.0)

