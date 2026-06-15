"""
Tests for embedded_vehicle.api.middleware — AuthMiddleware and RateLimiter.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from embedded_vehicle.api.middleware import AuthMiddleware, RateLimiter


def test_auth_middleware_blocks_without_token() -> None:
    app = FastAPI()
    app.add_middleware(AuthMiddleware, token="test_secret_123")

    @app.get("/protected")
    def _protected():
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/protected")
    assert resp.status_code == 401


def test_auth_middleware_allows_with_token() -> None:
    app = FastAPI()
    app.add_middleware(AuthMiddleware, token="test_secret_123")

    @app.get("/protected")
    def _protected():
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/protected", headers={"Authorization": "Bearer test_secret_123"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_auth_middleware_skips_health() -> None:
    app = FastAPI()
    app.add_middleware(AuthMiddleware, token="test_secret_123")

    @app.get("/health")
    def _health():
        return {"status": "up"}

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200


def test_rate_limiter_allows_under_limit() -> None:
    app = FastAPI()
    app.add_middleware(RateLimiter, max_requests=100, window_sec=60)

    @app.get("/")
    def _root():
        return {"ok": True}

    client = TestClient(app)
    for _ in range(5):
        resp = client.get("/")
        assert resp.status_code == 200


def test_rate_limiter_blocks_over_limit() -> None:
    app = FastAPI()
    app.add_middleware(RateLimiter, max_requests=2, window_sec=60)

    @app.get("/")
    def _root():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 429
