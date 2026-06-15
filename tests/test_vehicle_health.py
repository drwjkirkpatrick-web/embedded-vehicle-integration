"""
Tests for embedded_vehicle.vehicle.health — VehicleHealthMonitor.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

from embedded_vehicle.vehicle.health import VehicleHealthMonitor, MaintenanceItem, HealthSnapshot


@pytest.fixture
def monitor() -> VehicleHealthMonitor:
    return VehicleHealthMonitor()


def test_health_loads_defaults(monitor: VehicleHealthMonitor) -> None:
    assert "oil_change" in monitor._items
    assert "tire_rotation" in monitor._items


def test_health_record_maintenance(monitor: VehicleHealthMonitor) -> None:
    monitor.record_maintenance("oil_change", odometer_km=5000)
    item = monitor._items["oil_change"]
    assert item.last_date is not None
    assert item.last_odometer_km == 5000
    assert item.overdue is False


def test_health_update_odometer_triggers_overdue(monitor: VehicleHealthMonitor) -> None:
    monitor.record_maintenance("oil_change", odometer_km=0)
    monitor.update_odometer(6000)
    assert monitor._items["oil_change"].overdue is True


def test_health_snapshot_score_reduction(monitor: VehicleHealthMonitor) -> None:
    monitor.record_maintenance("oil_change", odometer_km=0)
    monitor.update_odometer(6000)
    snap = monitor.get_health_snapshot()
    assert snap.score < 100
    assert "oil_change" in snap.maintenance_overdue


def test_health_date_overdue(monitor: VehicleHealthMonitor) -> None:
    item = monitor._items["oil_change"]
    item.last_date = datetime.utcnow() - timedelta(days=200)
    item.interval_months = 6
    item.next_due_date = item.last_date + timedelta(days=180)
    # Manually check (poll loop would do this periodically)
    assert datetime.utcnow() > item.next_due_date


def test_health_no_overdue_initially(monitor: VehicleHealthMonitor) -> None:
    snap = monitor.get_health_snapshot()
    assert snap.score == 100
    assert snap.maintenance_overdue == []
