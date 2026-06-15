"""
embedded_vehicle/api/middleware.py
──────────────────────────────────
FastAPI middleware: JWT auth, rate limiting, CORS, and request logging.

Runs on the Raspberry Pi (or tunnel via ngrok / Tailscale Funnel for remote
access). All endpoints are local-first; remote access is opt-in.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import time
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("vehicle.api.middleware")


class AuthMiddleware(BaseHTTPMiddleware):
    """Simple bearer-token auth for local API."""

    def __init__(self, app: Any, token: str | None = None) -> None:
        super().__init__(app)
        self._token = token or secrets.token_urlsafe(32)
        logger.info("API auth token (save this): %s", self._token)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip auth for health-check and static docs
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != self._token:
            return Response("Unauthorized", status_code=401)
        return await call_next(request)


class RateLimiter(BaseHTTPMiddleware):
    """Per-IP sliding-window rate limiter."""

    def __init__(self, app: Any, max_requests: int = 60, window_sec: int = 60) -> None:
        super().__init__(app)
        self._max = max_requests
        self._window = window_sec
        self._clients: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        async with self._lock:
            ts = self._clients.setdefault(ip, [])
            # Prune old entries
            cutoff = now - self._window
            while ts and ts[0] < cutoff:
                ts.pop(0)
            if len(ts) >= self._max:
                return Response("Rate limited", status_code=429)
            ts.append(now)
        return await call_next(request)


def require_auth(token: str | None = None) -> AuthMiddleware:
    """Factory for AuthMiddleware with optional fixed token."""
    def _factory(app: Any) -> AuthMiddleware:
        return AuthMiddleware(app, token=token)
    return _factory
