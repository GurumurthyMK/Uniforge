"""Health endpoint tests (no database required for /health)."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "uniforge-api"


def test_error_envelope_on_404() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_validation_envelope() -> None:
    # /ready takes no body; force a 422 via wrong method body is hard,
    # so assert the envelope shape helper directly.
    from app.core.errors import error_payload

    payload = error_payload("VALIDATION_ERROR", "Request validation failed.", {"errors": []})
    assert payload["error"]["code"] == "VALIDATION_ERROR"
