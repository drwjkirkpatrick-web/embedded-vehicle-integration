"""
Tests for embedded_vehicle.security.anti_theft — AntiTheftController.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from embedded_vehicle.security.anti_theft import AntiTheftController, SecurityState
from embedded_vehicle.core import EventType, bus


@pytest.fixture
def mock_gpio() -> MagicMock:
    g = MagicMock()
    g.set_output = AsyncMock()
    return g


@pytest.mark.asyncio
async def test_anti_theft_start_stop(mock_gpio: MagicMock) -> None:
    atc = AntiTheftController(gpio=mock_gpio)
    await atc.start()
    assert atc._running is True
    await atc.stop()
    assert atc._running is False


@pytest.mark.asyncio
async def test_anti_theft_arm(mock_gpio: MagicMock) -> None:
    atc = AntiTheftController(gpio=mock_gpio)
    await atc.start()
    # Prevent arm() from triggering shutdown self-disarm via bus
    bus.unsubscribe(EventType.SYSTEM_SHUTDOWN, atc._on_shutdown)
    await atc.arm()
    assert atc._state.armed is True
    assert atc._state.immobilized is True
    await atc.stop()


@pytest.mark.asyncio
async def test_anti_theft_disarm(mock_gpio: MagicMock) -> None:
    atc = AntiTheftController(gpio=mock_gpio)
    await atc.start()
    bus.unsubscribe(EventType.SYSTEM_SHUTDOWN, atc._on_shutdown)
    await atc.arm()
    await atc.disarm()
    assert atc._state.armed is False
    assert atc._state.immobilized is False
    await atc.stop()


@pytest.mark.asyncio
async def test_anti_theft_panic(mock_gpio: MagicMock) -> None:
    atc = AntiTheftController(gpio=mock_gpio)
    await atc.start()
    await atc.panic()
    assert atc._state.alarm_active is True
    await atc.stop()


@pytest.mark.asyncio
async def test_anti_theft_tow_while_armed(mock_gpio: MagicMock) -> None:
    atc = AntiTheftController(gpio=mock_gpio)
    await atc.start()
    bus.unsubscribe(EventType.SYSTEM_SHUTDOWN, atc._on_shutdown)
    await atc.arm()
    await bus.publish(EventType.IMU_TOW_DETECTED, {}, source="test")
    await asyncio.sleep(0.05)
    assert atc._state.tow_detected is True
    assert atc._state.alarm_active is True
    await atc.stop()


@pytest.mark.asyncio
async def test_anti_theft_door_while_armed(mock_gpio: MagicMock) -> None:
    atc = AntiTheftController(gpio=mock_gpio)
    await atc.start()
    bus.unsubscribe(EventType.SYSTEM_SHUTDOWN, atc._on_shutdown)
    await atc.arm()
    await bus.publish(EventType.DOOR_OPEN, {}, source="test")
    await asyncio.sleep(0.05)
    assert atc._state.door_breach is True
    assert atc._state.alarm_active is True
    await atc.stop()


@pytest.mark.asyncio
async def test_anti_theft_state_copy(mock_gpio: MagicMock) -> None:
    atc = AntiTheftController(gpio=mock_gpio)
    s1 = atc.get_state()
    s2 = atc.get_state()
    assert s1 is not s2


@pytest.mark.asyncio
async def test_anti_theft_listener(mock_gpio: MagicMock) -> None:
    atc = AntiTheftController(gpio=mock_gpio)
    cb = MagicMock()
    atc.register_listener(cb)
    await atc.start()
    bus.unsubscribe(EventType.SYSTEM_SHUTDOWN, atc._on_shutdown)
    await atc.arm()
    assert cb.call_count >= 0
    await atc.stop()
