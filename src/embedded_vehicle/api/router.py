"""
embedded_vehicle/api/router.py
──────────────────────────────
FastAPI HTTP API exposing all vehicle subsystems for dashboard
integration, mobile apps, and remote diagnostics.

Endpoints:
    GET  /health          → HealthSnapshot JSON
    GET  /state           → Full vehicle state (engine, GPS, OBD, IMU)
    POST /engine/start    → Request engine start
    POST /engine/stop     → Request engine stop
    GET  /obd/snapshot    → Latest OBD PID values
    GET  /gps/fix         → Current GPS fix
    GET  /camera/snapshot → Capture JPEG
    POST /camera/lock     → Lock video buffer
    GET  /storage/stats   → Disk & DB stats
    GET  /gpio/relays     → Relay states
    POST /gpio/relay/{n}  → Set relay on/off
    GET  /events/recent   → Recent EventBus events
    POST /telegram/msg    → Send message via Telegram bot
    GET  /config          → Current configuration (redacted)
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from embedded_vehicle.core import EventType, bus
from embedded_vehicle.core.config import settings

logger = logging.getLogger("vehicle.api")

# Pydantic request/response models
class EngineCommand(BaseModel):
    action: str  # "start" | "stop"

class RelayCommand(BaseModel):
    name: str
    state: bool

class TelegramMsg(BaseModel):
    text: str


class APIServer:
    """FastAPI application wrapper for the vehicle integration."""

    def __init__(self) -> None:
        self.app = FastAPI(
            title="Embedded Vehicle API",
            description="Local REST API for Raspberry Pi vehicle telemetry",
            version="1.0.0",
            lifespan=self._lifespan,
        )
        self._build_routes()
        self._subsystems: dict[str, Any] = {}

    def attach(self, name: str, instance: Any) -> None:
        """Inject a subsystem so endpoints can query it."""
        self._subsystems[name] = instance

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """Startup / shutdown hooks."""
        logger.info("API server starting")
        yield
        logger.info("API server shutting down")

    def _build_routes(self) -> None:
        app = self.app

        @app.get("/health")
        async def health() -> dict[str, Any]:
            hm = self._subsystems.get("health")
            if hm:
                snap = hm.get_health_snapshot()
                return {"score": snap.score, "overdue": snap.maintenance_overdue,
                        "dtc_count": snap.dtc_count}
            return {"score": None, "note": "health monitor not attached"}

        @app.get("/state")
        async def state() -> dict[str, Any]:
            result: dict[str, Any] = {"engine": None, "gps": None, "obd": None, "imu": None}
            eng = self._subsystems.get("engine")
            if eng:
                result["engine"] = {
                    "ignition_on": eng._state.ignition_on,
                    "running": eng._state.engine_running,
                    "fuel_pump": eng._state.fuel_pump_on,
                }
            gps = self._subsystems.get("gps")
            if gps:
                fix = gps.get_latest_fix()
                result["gps"] = {"lat": fix.lat if fix else None, "lon": fix.lon if fix else None}
            obd = self._subsystems.get("obd")
            if obd:
                result["obd"] = {"connected": obd._connected, "protocol": obd._protocol}
            return result

        @app.post("/engine/start")
        async def engine_start() -> dict[str, Any]:
            eng = self._subsystems.get("engine")
            if not eng:
                raise HTTPException(503, detail="Engine controller unavailable")
            ok = await eng.request_start()
            return {"started": ok}

        @app.post("/engine/stop")
        async def engine_stop() -> dict[str, Any]:
            eng = self._subsystems.get("engine")
            if not eng:
                raise HTTPException(503, detail="Engine controller unavailable")
            ok = await eng.request_stop()
            return {"stopped": ok}

        @app.get("/obd/snapshot")
        async def obd_snapshot() -> dict[str, Any]:
            obd = self._subsystems.get("obd")
            if not obd:
                raise HTTPException(503, detail="OBD unavailable")
            snap = obd.get_latest_snapshot()
            # Convert dataclass to dict
            return snap.__dict__ if hasattr(snap, "__dataclass_fields__") else {}

        @app.get("/gps/fix")
        async def gps_fix() -> dict[str, Any]:
            gps = self._subsystems.get("gps")
            if not gps:
                raise HTTPException(503, detail="GPS unavailable")
            fix = gps.get_latest_fix()
            if not fix:
                raise HTTPException(404, detail="No GPS fix")
            return {"lat": fix.lat, "lon": fix.lon, "speed_kmh": fix.speed_kmh,
                    "heading": fix.heading_deg, "satellites": fix.satellites}

        @app.get("/camera/snapshot")
        async def camera_snapshot(camera: str = Query("front")) -> dict[str, Any]:
            cam = self._subsystems.get("camera")
            if not cam:
                raise HTTPException(503, detail="Camera unavailable")
            path = await cam.get_snapshot(camera)
            return {"snapshot_path": str(path)}

        @app.post("/camera/lock")
        async def camera_lock(reason: str = Query("manual"), duration: int = Query(60)) -> dict[str, Any]:
            cam = self._subsystems.get("camera")
            if not cam:
                raise HTTPException(503, detail="Camera unavailable")
            path = await cam.lock_buffer(reason, duration)
            return {"locked_path": str(path) if path else None}

        @app.get("/storage/stats")
        async def storage_stats() -> dict[str, Any]:
            import psutil
            try:
                usage = psutil.disk_usage(str(settings.storage.mount_point))
                return {"total_gb": usage.total / 1e9, "used_gb": usage.used / 1e9,
                        "free_gb": usage.free / 1e9, "percent": usage.percent}
            except Exception as exc:
                raise HTTPException(500, detail=str(exc))

        @app.get("/gpio/relays")
        async def gpio_relays() -> dict[str, Any]:
            gpio = self._subsystems.get("gpio")
            if not gpio:
                return {"note": "GPIO controller not attached"}
            return {"relay_states": gpio._relay_states, "input_states": gpio._input_states}

        @app.post("/gpio/relay/{name}")
        async def gpio_relay(name: str, cmd: RelayCommand) -> dict[str, Any]:
            gpio = self._subsystems.get("gpio")
            if not gpio:
                raise HTTPException(503, detail="GPIO unavailable")
            await gpio.set_output(name, cmd.state)
            return {"relay": name, "state": cmd.state}

        @app.get("/events/recent")
        async def events_recent(limit: int = Query(20, ge=1, le=100)) -> list[dict[str, Any]]:
            # Simple in-memory ring buffer via EventBus subscriber would be needed
            # for production; placeholder returns empty.
            return []

        @app.post("/telegram/msg")
        async def telegram_msg(msg: TelegramMsg) -> dict[str, Any]:
            tg = self._subsystems.get("telegram")
            if not tg:
                raise HTTPException(503, detail="Telegram bot unavailable")
            await tg.send_message(msg.text)
            return {"sent": True}

        @app.get("/config")
        async def config() -> dict[str, Any]:
            return {
                "vehicle_year": settings.vehicle.year,
                "vehicle_make": settings.vehicle.make,
                "obd_port": settings.obd.port,
                "gps_port": settings.gps.port,
                "camera_enabled": settings.camera.enabled,
                "audio_enabled": settings.audio.enabled,
                "telegram_enabled": settings.telegram.enabled,
            }
