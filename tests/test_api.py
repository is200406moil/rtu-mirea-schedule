from fastapi.testclient import TestClient

from app.api.api_v1.endpoints import schedule
from app.main import app


def test_healthcheck() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_refresh_requires_header(monkeypatch) -> None:
    monkeypatch.setattr(schedule, "SECRET_REFRESH_KEY", "test-key")

    with TestClient(app) as client:
        response = client.post("/api/refresh")

    assert response.status_code == 401
