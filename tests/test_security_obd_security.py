"""
Tests for embedded_vehicle.security.obd_security — OBDSecurityAudit.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from embedded_vehicle.security.obd_security import OBDSecurityAudit, OBDSession
from embedded_vehicle.core import EventType


@pytest.fixture
def audit() -> OBDSecurityAudit:
    return OBDSecurityAudit()


def test_audit_allows_all_when_disarmed(audit: OBDSecurityAudit) -> None:
    assert audit.audit_request("RPM") is True
    assert audit.audit_request("CLEAR_DTC") is True


def test_audit_allows_safe_pids_when_armed(audit: OBDSecurityAudit) -> None:
    audit.arm()
    assert audit.audit_request("RPM") is True
    assert audit.audit_request("SPEED") is True


def test_audit_blocks_unsafe_when_armed(audit: OBDSecurityAudit) -> None:
    audit.arm()
    assert audit.audit_request("FLASH_FIRMWARE") is False
    assert audit.audit_request("CLEAR_DTC") is False


def test_audit_log_session(audit: OBDSecurityAudit) -> None:
    session = OBDSession(
        start_time="2024-01-01T00:00:00",
        source="bt_adapter",
        pids_requested=["RPM"],
        authorized=False,
    )
    audit.log_session(session)
    assert len(audit._sessions) == 1


def test_audit_disarm_restores_access(audit: OBDSecurityAudit) -> None:
    audit.arm()
    assert audit.audit_request("CLEAR_DTC") is False
    audit.disarm()
    assert audit.audit_request("CLEAR_DTC") is True


@pytest.mark.asyncio
async def test_audit_on_connect_when_armed(audit: OBDSecurityAudit) -> None:
    await audit.start()
    audit.arm()
    # Publish OBD_CONNECTED event
    from embedded_vehicle.core import bus
    await bus.publish(EventType.OBD_CONNECTED, {}, source="test")
    await audit.stop()
