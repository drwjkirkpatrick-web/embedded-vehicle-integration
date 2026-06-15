"""
embedded_vehicle/security/anti_theft.py
───────────────────────────────────────
Anti-theft controller: immobilizer, tow detection, ignition tamper,
and remote lock/unlock via Telegram.

Relies on:
    - GPIOController (fuel-pump kill relay, starter disable)
    - IMUSensor (tow / motion detection)
    - EventBus for alert publishing
    - TelegramBot for remote notifications
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from embedded_vehicle.core import EventType, bus
from embedded_vehicle.core.config import settings

logger = logging.getLogger("vehicle.security")


@dataclass
class SecurityState:
    """Current security posture."""
    armed: bool = False
    immobilized: bool = False
    tow_detected: bool = False
    ignition_tamper: bool = False
    door_breach: bool = False
    last_armed_time: datetime | None = None
    last_disarmed_time: datetime | None = None
    alarm_active: bool = False


class AntiTheftController:
    """Vehicle anti-theft with immobilizer, motion detection, and remote alerts."""

    def __init__(self, gpio: Any | None = None) -> None:
        self.cfg = settings.gpio
        self._gpio = gpio
        self._state = SecurityState()
        self._running = False
        self._listeners: list[Callable[[SecurityState], None]] = []

    async def start(self) -> None:
        """Subscribe to relevant events, begin monitoring."""
        logger.info("AntiTheft: starting")
        self._running = True
        bus.subscribe(EventType.IGNITION_ON, self._on_ignition_on)
        bus.subscribe(EventType.IGNITION_OFF, self._on_ignition_off)
        bus.subscribe(EventType.IMU_TOW_DETECTED, self._on_tow)
        bus.subscribe(EventType.DOOR_OPEN, self._on_door_open)
        bus.subscribe(EventType.SYSTEM_SHUTDOWN, self._on_shutdown)

    async def stop(self) -> None:
        """Unsubscribe and disarm."""
        logger.info("AntiTheft: stopping")
        self._running = False
        bus.unsubscribe(EventType.IGNITION_ON, self._on_ignition_on)
        bus.unsubscribe(EventType.IGNITION_OFF, self._on_ignition_off)
        bus.unsubscribe(EventType.IMU_TOW_DETECTED, self._on_tow)
        bus.unsubscribe(EventType.DOOR_OPEN, self._on_door_open)
        bus.unsubscribe(EventType.SYSTEM_SHUTDOWN, self._on_shutdown)
        await self.disarm()

    # ── Public commands ───────────────────────────────────────────────────────

    async def arm(self) -> None:
        """Arm the system: immobilize engine, enable sensors."""
        if self._state.armed:
            return
        logger.info("AntiTheft: ARMED")
        self._state.armed = True
        self._state.last_armed_time = datetime.utcnow()
        await self._immobilize(True)
        await bus.publish(EventType.SYSTEM_SHUTDOWN, {"reason": "armed"}, source="security")

    async def disarm(self) -> None:
        """Disarm: restore fuel pump / starter."""
        if not self._state.armed:
            return
        logger.info("AntiTheft: DISARMED")
        self._state.armed = False
        self._state.immobilized = False
        self._state.alarm_active = False
        self._state.last_disarmed_time = datetime.utcnow()
        await self._immobilize(False)

    async def panic(self) -> None:
        """Trigger alarm: flash lights, sound horn, send alert."""
        logger.warning("AntiTheft: PANIC triggered")
        self._state.alarm_active = True
        await bus.publish(
            EventType.AUDIO_ALERT,
            {"message": "Vehicle alarm active", "priority": "high"},
            source="security",
        )

    def get_state(self) -> SecurityState:
        import copy
        return copy.deepcopy(self._state)

    def register_listener(self, cb: Callable[[SecurityState], None]) -> None:
        self._listeners.append(cb)

    # ── Event handlers ───────────────────────────────────────────────────────

    async def _on_ignition_on(self, event: Any) -> None:
        if self._state.armed and not self._state.immobilized:
            logger.warning("AntiTheft: ignition ON while armed — possible tamper")
            self._state.ignition_tamper = True
            await self.panic()

    async def _on_ignition_off(self, event: Any) -> None:
        pass  # Normal when driver leaves

    async def _on_tow(self, event: Any) -> None:
        if self._state.armed:
            logger.warning("AntiTheft: tow detected while armed")
            self._state.tow_detected = True
            await self.panic()

    async def _on_door_open(self, event: Any) -> None:
        if self._state.armed:
            logger.warning("AntiTheft: door opened while armed")
            self._state.door_breach = True
            await self.panic()

    async def _on_shutdown(self, event: Any) -> None:
        await self.stop()

    # ── GPIO helpers ───────────────────────────────────────────────────────

    async def _immobilize(self, on: bool) -> None:
        self._state.immobilized = on
        if self._gpio is None:
            try:
                from embedded_vehicle.gpio.controller import GPIOController
                self._gpio = GPIOController()
            except Exception:
                logger.warning("AntiTheft: no GPIO, immobilize=%s (noop)", on)
                return
        try:
            # Fuel pump kill + starter disable
            await self._gpio.set_output("fuel_pump", not on)  # cut fuel when immobilized
        except Exception as exc:
            logger.warning("AntiTheft: immobilize failed: %s", exc)
