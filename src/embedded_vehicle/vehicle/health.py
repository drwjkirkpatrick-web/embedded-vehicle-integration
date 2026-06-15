"""
embedded_vehicle/vehicle/health.py
──────────────────────────────────
Vehicle health monitoring: maintenance schedules, battery voltage,
oil pressure, coolant trends, and predictive alerts.

Uses:
    - StorageManager for historical data
    - OBDInterface for live PIDs
    - EventBus for alert publishing
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from embedded_vehicle.core import EventType, bus
from embedded_vehicle.core.config import settings

logger = logging.getLogger("vehicle.health")


@dataclass
class MaintenanceItem:
    """A single maintenance schedule item."""
    name: str
    interval_km: float | None = None
    interval_months: int | None = None
    last_odometer_km: float = 0.0
    last_date: datetime | None = None
    next_due_km: float | None = None
    next_due_date: datetime | None = None
    overdue: bool = False


@dataclass
class HealthSnapshot:
    """Aggregated vehicle health snapshot."""
    battery_voltage: float | None = None
    coolant_temp_c: float | None = None
    oil_pressure_psi: float | None = None
    brake_pad_pct: float | None = None
    tire_pressure_psi: list[float] = field(default_factory=list)
    dtc_count: int = 0
    dtcs: list[str] = field(default_factory=list)
    maintenance_overdue: list[str] = field(default_factory=list)
    score: int = 100  # 0-100 health score
    timestamp: datetime = field(default_factory=datetime.utcnow)


class VehicleHealthMonitor:
    """Tracks maintenance intervals and synthesizes a health score."""

    # Maintenance intervals for 1996 Toyota 5S-FE
    DEFAULT_ITEMS: list[MaintenanceItem] = [
        MaintenanceItem(name="oil_change", interval_km=5000, interval_months=6),
        MaintenanceItem(name="tire_rotation", interval_km=7500, interval_months=12),
        MaintenanceItem(name="brake_inspection", interval_km=15000, interval_months=12),
        MaintenanceItem(name="coolant_flush", interval_km=30000, interval_months=24),
        MaintenanceItem(name="spark_plugs", interval_km=30000, interval_months=24),
        MaintenanceItem(name="timing_belt", interval_km=90000, interval_months=60),
        MaintenanceItem(name="air_filter", interval_km=15000, interval_months=12),
        MaintenanceItem(name="fuel_filter", interval_km=30000, interval_months=24),
        MaintenanceItem(name="transmission_flush", interval_km=30000, interval_months=24),
    ]

    def __init__(self, storage: Any | None = None) -> None:
        self.cfg = settings.vehicle
        self._storage = storage
        self._items: dict[str, MaintenanceItem] = {}
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        self._last_odometer_km: float = 0.0
        self._load_defaults()

    def _load_defaults(self) -> None:
        import copy
        for item in copy.deepcopy(self.DEFAULT_ITEMS):
            self._items[item.name] = item

    async def start(self) -> None:
        """Begin periodic health polling."""
        logger.info("HealthMonitor: starting")
        self._running = True
        self._monitor_task = asyncio.create_task(self._health_poll_loop())
        bus.subscribe(EventType.OBD_CEL_ON, self._on_cel)

    async def stop(self) -> None:
        """Stop monitoring."""
        logger.info("HealthMonitor: stopping")
        self._running = False
        bus.unsubscribe(EventType.OBD_CEL_ON, self._on_cel)
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    # ── Public API ──────────────────────────────────────────────────────────

    def get_health_snapshot(self) -> HealthSnapshot:
        """Build a current health snapshot."""
        snap = HealthSnapshot()
        # Check maintenance
        overdue = []
        for name, item in self._items.items():
            if item.overdue:
                overdue.append(name)
        snap.maintenance_overdue = overdue
        snap.score = max(0, 100 - len(overdue) * 10 - snap.dtc_count * 15)
        return snap

    def record_maintenance(self, name: str, odometer_km: float | None = None) -> None:
        """Mark a maintenance item as completed now."""
        item = self._items.get(name)
        if not item:
            logger.warning("HealthMonitor: unknown maintenance item %s", name)
            return
        now = datetime.utcnow()
        item.last_date = now
        if odometer_km is not None:
            item.last_odometer_km = odometer_km
        # Recalculate next due
        if item.interval_months:
            item.next_due_date = now + timedelta(days=item.interval_months * 30)
        if item.interval_km and odometer_km is not None:
            item.next_due_km = odometer_km + item.interval_km
        item.overdue = False
        logger.info("HealthMonitor: recorded %s at %.0f km", name, odometer_km or 0)

    def update_odometer(self, km: float) -> None:
        """Update odometer and check mileage-based maintenance."""
        self._last_odometer_km = km
        for name, item in self._items.items():
            if item.next_due_km is not None and km >= item.next_due_km:
                item.overdue = True
                logger.warning("HealthMonitor: %s overdue (%.0f km)", name, km)

    # ── Event handlers ───────────────────────────────────────────────────────

    async def _on_cel(self, event: Any) -> None:
        logger.warning("HealthMonitor: CEL on — health score reduced")

    # ── Background loop ───────────────────────────────────────────────────────

    async def _health_poll_loop(self) -> None:
        """Poll every 60 seconds for health changes."""
        while self._running:
            await asyncio.sleep(60)
            # Check date-based maintenance
            now = datetime.utcnow()
            for name, item in self._items.items():
                if item.next_due_date and now >= item.next_due_date:
                    if not item.overdue:
                        item.overdue = True
                        logger.warning("HealthMonitor: %s overdue (date)", name)
                        await bus.publish(
                            EventType.MAINTENANCE_DUE,
                            {"item": name, "type": "date"},
                            source="health",
                        )
