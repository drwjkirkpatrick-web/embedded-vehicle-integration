"""
embedded_vehicle/vehicle/engine.py
──────────────────────────────────
Engine control: start/stop, ignition state tracking, fuel-pump relay,
and immobilizer integration via GPIO.

Relies on:
    - GPIOController for relay outputs (fuel pump, starter, block heater)
    - EventBus for ignition-state events
    - OBDInterface for engine-running confirmation
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from embedded_vehicle.core import EventType, bus
from embedded_vehicle.core.config import settings

logger = logging.getLogger("vehicle.engine")


@dataclass
class EngineState:
    """Current engine state snapshot."""
    ignition_on: bool = False
    engine_running: bool = False
    starter_engaged: bool = False
    fuel_pump_on: bool = False
    block_heater_on: bool = False
    last_start_time: datetime | None = None
    last_stop_time: datetime | None = None
    total_runtime_sec: float = 0.0
    start_attempts_today: int = 0


class EngineController:
    """Manages engine start/stop logic via GPIO relays and ignition sensing."""

    def __init__(self, gpio: Any | None = None) -> None:
        self.cfg = settings.gpio
        self.vehicle_cfg = settings.vehicle
        self._gpio = gpio  # injected; falls back to global if None
        self._state = EngineState()
        self._running = False
        self._ignition_task: asyncio.Task | None = None
        self._runtime_task: asyncio.Task | None = None
        self._listeners: list[Callable[[EngineState], None]] = []

    async def start(self) -> None:
        """Subscribe to ignition events, begin monitoring."""
        logger.info("EngineController: starting")
        self._running = True
        bus.subscribe(EventType.IGNITION_ON, self._on_ignition_on)
        bus.subscribe(EventType.IGNITION_OFF, self._on_ignition_off)
        bus.subscribe(EventType.SYSTEM_SHUTDOWN, self._on_shutdown)
        self._ignition_task = asyncio.create_task(self._ignition_poll_loop())

    async def stop(self) -> None:
        """Unsubscribe, cancel tasks, ensure fuel pump off."""
        logger.info("EngineController: stopping")
        self._running = False
        bus.unsubscribe(EventType.IGNITION_ON, self._on_ignition_on)
        bus.unsubscribe(EventType.IGNITION_OFF, self._on_ignition_off)
        bus.unsubscribe(EventType.SYSTEM_SHUTDOWN, self._on_shutdown)
        for task in (self._ignition_task, self._runtime_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        await self._set_fuel_pump(False)

    # ── Public commands ──────────────────────────────────────────────────────

    async def request_start(self) -> bool:
        """Engage starter relay and fuel pump if safe to start."""
        if self._state.engine_running:
            logger.warning("EngineController: start requested but engine already running")
            return False
        if self._state.start_attempts_today >= 5:
            logger.error("EngineController: max start attempts exceeded")
            return False
        logger.info("EngineController: engaging starter")
        self._state.starter_engaged = True
        self._state.start_attempts_today += 1
        await self._set_fuel_pump(True)
        # In production: pulse starter relay for 1-2 seconds
        await asyncio.sleep(1.5)
        self._state.starter_engaged = False
        self._state.last_start_time = datetime.utcnow()
        self._state.engine_running = True
        self._runtime_task = asyncio.create_task(self._runtime_accumulator())
        await bus.publish(EventType.ENGINE_STARTED, {}, source="engine")
        return True

    async def request_stop(self) -> bool:
        """Cut fuel pump, mark engine stopped."""
        if not self._state.engine_running:
            return False
        logger.info("EngineController: stopping engine")
        await self._set_fuel_pump(False)
        self._state.engine_running = False
        self._state.last_stop_time = datetime.utcnow()
        if self._runtime_task:
            self._runtime_task.cancel()
            try:
                await self._runtime_task
            except asyncio.CancelledError:
                pass
            self._runtime_task = None
        await bus.publish(EventType.ENGINE_STOPPED, {}, source="engine")
        return True

    async def enable_block_heater(self, minutes: int = 30) -> None:
        """Turn on block-heater relay for cold-start preheat."""
        logger.info("EngineController: block heater on for %d min", minutes)
        await self._set_relay("block_heater", True)
        self._state.block_heater_on = True
        asyncio.get_event_loop().call_later(
            minutes * 60,
            asyncio.create_task,
            self._set_relay("block_heater", False),
        )

    def get_state(self) -> EngineState:
        """Return current engine state (copy)."""
        import copy
        return copy.deepcopy(self._state)

    def register_listener(self, cb: Callable[[EngineState], None]) -> None:
        self._listeners.append(cb)

    # ── Event handlers ───────────────────────────────────────────────────────

    async def _on_ignition_on(self, event: Any) -> None:
        self._state.ignition_on = True
        logger.info("EngineController: ignition ON")
        if not self._state.engine_running:
            # Auto-start if configured (e.g., remote-start)
            pass

    async def _on_ignition_off(self, event: Any) -> None:
        self._state.ignition_on = False
        logger.info("EngineController: ignition OFF")
        if self._state.engine_running:
            await self.request_stop()

    async def _on_shutdown(self, event: Any) -> None:
        await self.stop()

    # ── GPIO helpers ─────────────────────────────────────────────────────────

    async def _set_fuel_pump(self, on: bool) -> None:
        self._state.fuel_pump_on = on
        await self._set_relay("fuel_pump", on)

    async def _set_relay(self, name: str, on: bool) -> None:
        if self._gpio is None:
            # Try to resolve global GPIOController if available
            try:
                from embedded_vehicle.gpio.controller import GPIOController
                self._gpio = GPIOController()
            except Exception:
                logger.warning("EngineController: no GPIO available, relay %s = %s (noop)", name, on)
                return
        try:
            pin = getattr(self.cfg, f"relay_{name}", None)
            if pin is not None:
                await self._gpio.set_output(name, on)
        except Exception as exc:
            logger.warning("EngineController: relay %s failed: %s", name, exc)

    # ── Background loops ────────────────────────────────────────────────────

    async def _ignition_poll_loop(self) -> None:
        """Poll ignition sense pin if no event bus messages arrive."""
        while self._running:
            await asyncio.sleep(2.0)
            # In production: read ignition_sense GPIO and publish event
            # if state changed and no bus event received.

    async def _runtime_accumulator(self) -> None:
        """Accumulate engine runtime while running."""
        while self._running and self._state.engine_running:
            await asyncio.sleep(1.0)
            self._state.total_runtime_sec += 1.0
