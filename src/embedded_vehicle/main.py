"""
embedded_vehicle/main.py
────────────────
Main daemon orchestrator for the Embedded-Vehicle integration.

Starts all subsystems in order:
1. Logging + config
2. Event bus (global singleton already exists)
3. Storage (SQLite)
4. GPIO (relays + inputs)
5. OBD-II
6. GPS
7. IMU
8. Camera
9. Audio / Voice Assistant
10. Telegram Bot

Handles graceful shutdown on SIGINT/SIGTERM.

Usage:
    vehicle-daemon        # foreground
    vehicle-daemon &     # background (or use systemd)
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from contextlib import AsyncExitStack

from embedded_vehicle.audio.assistant import VoiceAssistant
from embedded_vehicle.camera.recorder import CameraRecorder
from embedded_vehicle.core import bus, setup_logging
from embedded_vehicle.core.config import settings
from embedded_vehicle.gps.tracker import GPSTracker
from embedded_vehicle.gpio.controller import GPIOController
from embedded_vehicle.imu.sensor import IMUSensor
from embedded_vehicle.obd.interface import OBDInterface
from embedded_vehicle.storage.manager import StorageManager
from embedded_vehicle.telegram.bot import TelegramBot

logger = logging.getLogger("vehicle.main")


class VehicleDaemon:
    """Orchestrates all vehicle subsystems."""

    def __init__(self) -> None:
        self._shutdown_event = asyncio.Event()
        self._stack = AsyncExitStack()

        # Subsystem instances
        self.storage = StorageManager()
        self.gpio = GPIOController()
        self.obd = OBDInterface()
        self.gps = GPSTracker()
        self.imu = IMUSensor()
        self.camera = CameraRecorder()
        self.audio = VoiceAssistant()
        self.telegram = TelegramBot()

    async def run(self) -> None:
        """Main entry: setup, start all, wait for shutdown."""
        setup_logging()
        settings.ensure_dirs()
        logger.info("=" * 60)
        logger.info("Hermes Vehicle Daemon starting")
        logger.info("Vehicle: %d %s %s (%s)",
                     settings.vehicle.year,
                     settings.vehicle.make,
                     settings.vehicle.model,
                     settings.vehicle.engine)
        logger.info("=" * 60)

        # Register signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._request_shutdown)

        try:
            await self._start_all()
            await self._shutdown_event.wait()
        finally:
            await self._stop_all()
            logger.info("Hermes Vehicle Daemon stopped")

    def _request_shutdown(self) -> None:
        """Signal handler: trigger graceful shutdown."""
        logger.info("Shutdown signal received")
        self._shutdown_event.set()

    # ── Start sequence ──────────────────────────────────────────────────────

    async def _start_all(self) -> None:
        """Start all subsystems in dependency order."""
        logger.info("Starting subsystems...")

        # 1. Storage first (others may log to it)
        await self.storage.start()
        logger.info("✓ Storage")

        # 2. GPIO (ignition sense, relays)
        await self.gpio.start()
        logger.info("✓ GPIO")

        # 3. OBD-II (engine telemetry)
        await self.obd.start()
        logger.info("✓ OBD-II")

        # 4. GPS (location)
        await self.gps.start()
        logger.info("✓ GPS")

        # 5. IMU (motion, collision)
        await self.imu.start()
        logger.info("✓ IMU")

        # 6. Camera (dashcam)
        await self.camera.start()
        logger.info("✓ Camera")

        # 7. Audio (voice assistant)
        await self.audio.start()
        logger.info("✓ Audio")

        # 8. Telegram (remote control)
        await self.telegram.start()
        logger.info("✓ Telegram")

        # Wire IMU to ignition state (for tow detection)
        # In production: subscribe GPIO ignition events to IMU
        logger.info("All subsystems started successfully")

    # ── Stop sequence ─────────────────────────────────────────────────────────

    async def _stop_all(self) -> None:
        """Stop all subsystems in reverse order."""
        logger.info("Stopping subsystems...")

        # Reverse order of startup
        try:
            await self.telegram.stop()
            logger.info("✗ Telegram")
        except Exception:
            logger.exception("Error stopping Telegram")

        try:
            await self.audio.stop()
            logger.info("✗ Audio")
        except Exception:
            logger.exception("Error stopping Audio")

        try:
            await self.camera.stop()
            logger.info("✗ Camera")
        except Exception:
            logger.exception("Error stopping Camera")

        try:
            await self.imu.stop()
            logger.info("✗ IMU")
        except Exception:
            logger.exception("Error stopping IMU")

        try:
            await self.gps.stop()
            logger.info("✗ GPS")
        except Exception:
            logger.exception("Error stopping GPS")

        try:
            await self.obd.stop()
            logger.info("✗ OBD-II")
        except Exception:
            logger.exception("Error stopping OBD-II")

        try:
            await self.gpio.shutdown()
            logger.info("✗ GPIO")
        except Exception:
            logger.exception("Error stopping GPIO")

        try:
            await self.storage.close()
            logger.info("✗ Storage")
        except Exception:
            logger.exception("Error stopping Storage")


def main() -> None:
    """CLI entry point: vehicle-daemon"""
    daemon = VehicleDaemon()
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    sys.exit(0)


if __name__ == "__main__":
    main()
