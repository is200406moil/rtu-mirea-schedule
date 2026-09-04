import os
import uuid

import pytest
from pymongo import AsyncMongoClient

from app.crud import schedule as schedule_crud
from app.models.schedule import ScheduleByWeekdaysModel, ScheduleLessonsModel

TEST_MONGODB_URL = os.getenv("TEST_MONGODB_URL")


def _empty_schedule() -> ScheduleByWeekdaysModel:
    return ScheduleByWeekdaysModel(
        monday=ScheduleLessonsModel(lessons=[]),
        tuesday=ScheduleLessonsModel(lessons=[]),
        wednesday=ScheduleLessonsModel(lessons=[]),
        thursday=ScheduleLessonsModel(lessons=[]),
        friday=ScheduleLessonsModel(lessons=[]),
        saturday=ScheduleLessonsModel(lessons=[]),
    )


@pytest.mark.skipif(not TEST_MONGODB_URL, reason="TEST_MONGODB_URL is not configured")
async def test_atomic_publish_and_distributed_refresh_lock(monkeypatch) -> None:
    database_name = f"schedule_test_{uuid.uuid4().hex}"
    monkeypatch.setattr(schedule_crud, "DATABASE_NAME", database_name)
    client = AsyncMongoClient(TEST_MONGODB_URL, tz_aware=True)

    try:
        database = client[database_name]
        await database[schedule_crud.SCHEDULE_COLLECTION_NAME].insert_one(
            {"group": "OLD", "schedule": {}}
        )

        await schedule_crud.replace_all_schedules(
            client,
            {
                "ИКБО-14-23": _empty_schedule(),
                "ИКБО-15-23": _empty_schedule(),
            },
        )

        groups = await database[schedule_crud.SCHEDULE_COLLECTION_NAME].distinct("group")
        assert set(groups) == {"ИКБО-14-23", "ИКБО-15-23"}
        index = await database[schedule_crud.SCHEDULE_COLLECTION_NAME].index_information()
        assert any(spec.get("unique") for spec in index.values())

        assert await schedule_crud.acquire_refresh_lock(
            client,
            owner="worker-one",
            ttl_seconds=60,
        )
        assert not await schedule_crud.acquire_refresh_lock(
            client,
            owner="worker-two",
            ttl_seconds=60,
        )
        await schedule_crud.set_refresh_status(
            client,
            state="running",
            message="Refresh in progress",
        )
        status = await schedule_crud.get_refresh_status(client)
        assert status["running"] is True

        await schedule_crud.release_refresh_lock(client, owner="worker-one")
        assert await schedule_crud.acquire_refresh_lock(
            client,
            owner="worker-two",
            ttl_seconds=60,
        )
    finally:
        await client.drop_database(database_name)
        await client.close()
