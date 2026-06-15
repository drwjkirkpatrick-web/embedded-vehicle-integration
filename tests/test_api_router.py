"""
Tests for embedded_vehicle.api.router — APIServer with mocked subsystems.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from embedded_vehicle.api.router import APIServer


@pytest.fixture
def api() -> APIServer:
    srv = APIServer()
    return srv


@pytest.fixture
def client(api: APIServer) -> Any:
    return TestClient(api.app)


def test_api_health_no_health_monitor(client: Any) -> None:
    """Health endpoint should return a note when health monitor is unattached."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] is None
    assert "note" in data


def test_api_state_empty(client: Any) -> None:
    resp = client.get("/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["engine"] is None


def test_api_config(client: Any) -> None:
    resp = client.get("/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["vehicle_year"] == 1996
    assert data["vehicle_make"] == "Toyota"


def test_api_storage_stats(client: Any) -> None:
    """Storage stats should return disk usage or a 500 if psutil fails."""
    resp = client.get("/storage/stats")
    assert resp.status_code in (200, 500)


def test_api_gpio_relay_unattached(client: Any) -> None:
    """Relay endpoint returns note when GPIO not attached."""
    resp = client.get("/gpio/relays")
    assert resp.status_code == 200
    data = resp.json()
    assert "note" in data


def test_api_engine_start_unattached(client: Any) -> None:
    resp = client.post("/engine/start")
    assert resp.status_code == 503


def test_api_engine_stop_unattached(client: Any) -> None:
    resp = client.post("/engine/stop")
    assert resp.status_code == 503


def test_api_camera_snapshot_unattached(client: Any) -> None:
    resp = client.get("/camera/snapshot")
    assert resp.status_code == 503


def test_api_gps_fix_unattached(client: Any) -> None:
    resp = client.get("/gps/fix")
    assert resp.status_code == 503


def test_api_telegram_unattached(client: Any) -> None:
    resp = client.post("/telegram/msg", json={"text": "hello"})
    assert resp.status_code == 503


def test_api_with_mocked_engine(api: APIServer, client: Any) -> None:
    """Attach a mock engine controller and test start/stop."""
    mock_eng = MagicMock()
    mock_eng._state = MagicMock()
    mock_eng._state.ignition_on = True
    mock_eng._state.engine_running = True
    mock_eng._state.fuel_pump_on = True
    mock_eng.request_start = AsyncMock(return_value=True)
    mock_eng.request_stop = AsyncMock(return_value=True)
    api.attach("engine", mock_eng)

    resp = client.get("/state")
    assert resp.status_code == 200
    assert resp.json()["engine"]["running"] is True

    resp = client.post("/engine/start")
    assert resp.status_code == 200
    assert resp.json()["started"] is True

    resp = client.post("/engine/stop")
    assert resp.status_code == 200
    assert resp.json()["stopped"] is True
