from fastapi.testclient import TestClient
from pymongo.errors import PyMongoError

from app.api.api_v1.endpoints import schedule
from app.database.database import get_database
from app.main import app


def test_healthcheck() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_check_confirms_mongodb_connection() -> None:
    class AvailableAdmin:
        async def command(self, name: str) -> dict[str, int]:
            assert name == "ping"
            return {"ok": 1}

    class AvailableDatabase:
        admin = AvailableAdmin()

    app.dependency_overrides[get_database] = lambda: AvailableDatabase()
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        app.dependency_overrides.pop(get_database, None)

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_check_reports_mongodb_failure() -> None:
    class UnavailableAdmin:
        async def command(self, _name: str) -> None:
            raise PyMongoError("database unavailable")

    class UnavailableDatabase:
        admin = UnavailableAdmin()

    app.dependency_overrides[get_database] = lambda: UnavailableDatabase()
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        app.dependency_overrides.pop(get_database, None)

    assert response.status_code == 503
    assert response.json() == {"detail": "MongoDB is unavailable"}


def test_refresh_requires_header(monkeypatch) -> None:
    monkeypatch.setattr(schedule, "SECRET_REFRESH_KEY", "test-key")

    with TestClient(app) as client:
        response = client.post("/api/refresh")

    assert response.status_code == 401


def test_refresh_uses_shared_lock_and_reports_conflict(monkeypatch) -> None:
    monkeypatch.setattr(schedule, "SECRET_REFRESH_KEY", "test-key")

    async def lock_is_busy(*args, **kwargs):
        return False

    monkeypatch.setattr(schedule, "acquire_refresh_lock", lock_is_busy)

    with TestClient(app) as client:
        response = client.post(
            "/api/refresh",
            headers={"X-Refresh-Key": "test-key"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Schedule refresh is already running"


def test_refresh_starts_background_job_and_reads_persisted_status(monkeypatch) -> None:
    monkeypatch.setattr(schedule, "SECRET_REFRESH_KEY", "test-key")
    status_updates = []

    async def acquire_lock(*args, **kwargs):
        return True

    async def set_status(*args, **kwargs):
        status_updates.append(kwargs)

    async def run_refresh(*args, **kwargs):
        return None

    async def read_status(*args, **kwargs):
        return {
            "running": True,
            "detail": {"state": "running", "message": "Refresh in progress"},
        }

    monkeypatch.setattr(schedule, "acquire_refresh_lock", acquire_lock)
    monkeypatch.setattr(schedule, "set_refresh_status", set_status)
    monkeypatch.setattr(schedule, "_run_refresh", run_refresh)
    monkeypatch.setattr(schedule, "get_refresh_status", read_status)

    with TestClient(app) as client:
        started = client.post(
            "/api/refresh",
            headers={"X-Refresh-Key": "test-key"},
        )
        current = client.get(
            "/api/refresh/status",
            headers={"X-Refresh-Key": "test-key"},
        )

    assert started.status_code == 202
    assert started.json()["status"] == "started"
    assert status_updates[0]["state"] == "running"
    assert current.status_code == 200
    assert current.json()["running"] is True


async def test_refresh_failure_is_recorded_and_lock_is_released(monkeypatch) -> None:
    events = []

    async def fail_parse(_):
        raise RuntimeError("upstream unavailable")

    async def set_status(*args, **kwargs):
        events.append(("status", kwargs["state"], kwargs["message"]))

    async def release_lock(*args, **kwargs):
        events.append(("release", kwargs["owner"]))

    monkeypatch.setattr(schedule, "parse_schedule", fail_parse)
    monkeypatch.setattr(schedule, "set_refresh_status", set_status)
    monkeypatch.setattr(schedule, "release_refresh_lock", release_lock)

    await schedule._run_refresh(object(), "worker-one")

    assert events == [
        (
            "status",
            "failed",
            "Refresh failed; the previous dataset is still active",
        ),
        ("release", "worker-one"),
    ]
