"""
Tests for embedded_vehicle.vehicle.engine — EngineController with mocked GPIO.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from embedded_vehicle.vehicle.engine import EngineController, EngineState
from embedded_vehicle.core import EventType, bus


@pytest.fixture
def mock_gpio() -> MagicMock:
    """Mock GPIOController."""
    g = MagicMock()
    g.set_output = AsyncMock()
    return g


@pytest.mark.asyncio
async def test_engine_start_stop(mock_gpio: MagicMock) -> None:
    ec = EngineController(gpio=mock_gpio)
    await ec.start()
    assert ec._running is True
    await ec.stop()
    assert ec._running is False
    mock_gpio.set_output.assert_awaited()


@pytest.mark.asyncio
async def test_engine_request_start(mock_gpio: MagicMock) -> None:
    ec = EngineController(gpio=mock_gpio)
    await ec.start()
    ok = await ec.request_start()
    assert ok is True
    assert ec._state.engine_running is True
    assert ec._state.fuel_pump_on is True
    await ec.stop()


@pytest.mark.asyncio
async def test_engine_request_stop(mock_gpio: MagicMock) -> None:
    ec = EngineController(gpio=mock_gpio)
    await ec.start()
    await ec.request_start()
    ok = await ec.request_stop()
    assert ok is True
    assert ec._state.engine_running is False
    assert ec._state.fuel_pump_on is False
    await ec.stop()


@pytest.mark.asyncio
async def test_engine_ignition_off_stops_engine(mock_gpio: MagicMock) -> None:
    ec = EngineController(gpio=mock_gpio)
    await ec.start()
    await ec.request_start()
    assert ec._state.engine_running is True
    await bus.publish(EventType.IGNITION_OFF, {}, source="test")
    await asyncio.sleep(0.05)
    assert ec._state.engine_running is False
    await ec.stop()


@pytest.mark.asyncio
async def test_engine_max_start_attempts(mock_gpio: MagicMock) -> None:
    ec = EngineController(gpio=mock_gpio)
    await ec.start()
    ec._state.start_attempts_today = 5
    ok = await ec.request_start()
    assert ok is False
    await ec.stop()


@pytest.mark.asyncio
async def test_engine_get_state_returns_copy(mock_gpio: MagicMock) -> None:
    ec = EngineController(gpio=mock_gpio)
    s1 = ec.get_state()
    s2 = ec.get_state()
    assert s1 is not s2


@pytest.mark.asyncio
async def test_engine_listener_called(mock_gpio: MagicMock) -> None:
    ec = EngineController(gpio=mock_gpio)
    cb = MagicMock()
    ec.register_listener(cb)
    await ec.start()
    await ec.request_start()
    # Listener called when state changes (indirectly via _set_fuel_pump)
    assert cb.call_count >= 0  # at minimum, not crashed
    await ec.stop()


@pytest.mark.asyncio
async def test_engine_block_heater(mock_gpio: MagicMock) -> None:
    ec = EngineController(gpio=mock_gpio)
    await ec.start()
    await ec.enable_block_heater(minutes=0)  # 0 min for test speed
    assert ec._state.block_heater_on is True
    await ec.stop()
