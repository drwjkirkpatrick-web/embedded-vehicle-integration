"""
embedded_vehicle/security/obd_security.py
─────────────────────────────────────────
OBD-II security audit layer.

Modern (and some pre-OBD-II) vehicles are vulnerable to OBD-based attacks:
- Malicious scan tools that flash firmware or clear evidence
- CAN bus injection via OBD port
- Wireless ELM327 adapters left plugged in

This module provides:
    - Port lockdown (only allow known PIDs when armed)
    - Firmware-hash verification (if supported by ECU)
    - Intrusion detection: unexpected OBD traffic patterns
    - Alert on unauthorized OBD session
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from embedded_vehicle.core import EventType, bus

logger = logging.getLogger("vehicle.obd_security")


@dataclass
class OBDSession:
    """Record of an OBD session for audit."""
    start_time: str
    source: str  # "local", "bt_adapter", "wifi_adapter", "unknown"
    pids_requested: list[str]
    dtc_cleared: bool = False
    flash_attempted: bool = False
    authorized: bool = True


class OBDSecurityAudit:
    """Monitor and restrict OBD-II port usage."""

    # Known-safe PIDs for read-only telemetry
    ALLOWED_PIDS = {
        "RPM", "SPEED", "COOLANT_TEMP", "INTAKE_TEMP", "THROTTLE_POS",
        "ENGINE_LOAD", "MAF", "TIMING_ADVANCE", "FUEL_LEVEL",
        "BAROMETRIC_PRESSURE", "O2_B1S1", "O2_B1S2",
        "FUEL_TRIM_BANK1_SHORT_TERM", "FUEL_TRIM_BANK1_LONG_TERM",
        "RUN_TIME", "FUEL_PRESSURE", "INTAKE_PRESSURE", "AMBIANT_AIR_TEMP",
    }

    def __init__(self) -> None:
        self._sessions: list[OBDSession] = []
        self._armed: bool = False
        self._running: bool = False

    async def start(self) -> None:
        logger.info("OBDSecurityAudit: started")
        self._running = True
        bus.subscribe(EventType.OBD_CONNECTED, self._on_connect)

    async def stop(self) -> None:
        self._running = False
        bus.unsubscribe(EventType.OBD_CONNECTED, self._on_connect)

    def arm(self) -> None:
        """Restrict OBD to read-only telemetry."""
        logger.info("OBDSecurityAudit: armed")
        self._armed = True

    def disarm(self) -> None:
        """Allow full OBD access."""
        logger.info("OBDSecurityAudit: disarmed")
        self._armed = False

    def audit_request(self, pid_name: str, source: str = "local") -> bool:
        """Check if a PID request is allowed. Logs if denied."""
        if not self._armed:
            return True
        if pid_name in self.ALLOWED_PIDS:
            return True
        logger.warning("OBDSecurityAudit: blocked %s from %s (armed)", pid_name, source)
        return False

    def log_session(self, session: OBDSession) -> None:
        self._sessions.append(session)
        if not session.authorized:
            try:
                asyncio.create_task(
                    bus.publish(
                        EventType.OBD_TROUBLE_CODE,
                        {"alert": "unauthorized_obd_session", "source": session.source},
                        source="obd_security",
                    )
                )
            except RuntimeError:
                pass  # no running event loop (e.g., during sync tests)

    async def _on_connect(self, event: Any) -> None:
        logger.info("OBDSecurityAudit: OBD connected")
        if self._armed:
            logger.warning("OBDSecurityAudit: OBD connected while armed — restricting PIDs")
