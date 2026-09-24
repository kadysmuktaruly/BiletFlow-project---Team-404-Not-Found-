"""App wiring: the error shape, CORS, health, and settings. No database needed.

The database-backed suite (separate *_test database) arrives with the auth work; these
tests stub the session so they can run anywhere.
"""

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings
from app.db import get_session
from app.main import API_PREFIX, create_app


class _FakeSession:
    def __init__(self, fail: bool) -> None:
        self.fail = fail

    async def execute(self, *_: Any) -> None:
        if self.fail:
            raise ConnectionRefusedError("database down")


def _client(fail_db: bool = False) -> httpx.AsyncClient:
    app = create_app()

    async def fake_session() -> AsyncIterator[_FakeSession]:
        yield _FakeSession(fail_db)

    app.dependency_overrides[get_session] = fake_session

    class Body(BaseModel):
        name: str = Field(min_length=1)

    @app.post(f"{API_PREFIX}/_echo")
    async def echo(body: Body) -> Body:
        return body

    @app.get(f"{API_PREFIX}/_boom")
    async def boom() -> None:
        raise RuntimeError("unexpected")

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_health_ok() -> None:
    async with _client() as client:
        response = await client.get(f"{API_PREFIX}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_reports_database_down_in_error_shape() -> None:
    async with _client(fail_db=True) as client:
        response = await client.get(f"{API_PREFIX}/health")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "service_unavailable",
            "message": "The database is unreachable.",
            "details": None,
        }
    }


async def test_unknown_route_uses_error_shape() -> None:
    async with _client() as client:
        response = await client.get(f"{API_PREFIX}/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_validation_error_uses_error_shape() -> None:
    async with _client() as client:
        response = await client.post(f"{API_PREFIX}/_echo", json={"name": ""})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["loc"] == ["body", "name"]
    assert set(error["details"][0]) == {"loc", "msg", "type"}


async def test_unhandled_exception_uses_error_shape() -> None:
    async with _client() as client:
        response = await client.get(f"{API_PREFIX}/_boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"


async def test_cors_allows_web_origin_with_credentials() -> None:
    async with _client() as client:
        response = await client.options(
            f"{API_PREFIX}/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"


async def test_cors_rejects_unknown_origin() -> None:
    async with _client() as client:
        response = await client.options(
            f"{API_PREFIX}/health",
            headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
        )
    assert "access-control-allow-origin" not in response.headers


def test_production_requires_real_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(environment="production", _env_file=None)
    ok = Settings(environment="production", jwt_secret="x" * 32, _env_file=None)
    assert ok.jwt_secret == "x" * 32


def test_cors_origin_list_includes_public_base_url_and_extras() -> None:
    settings = Settings(
        public_base_url="http://localhost:3000/",
        cors_origins="http://192.168.1.20:3000, http://localhost:3000",
        _env_file=None,
    )
    assert settings.cors_origin_list == ["http://localhost:3000", "http://192.168.1.20:3000"]
