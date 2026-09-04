import re
from collections.abc import Iterator
from typing import Any

from pymongo import AsyncMongoClient

from app.core.config import (
    DATABASE_NAME,
    SCHEDULE_COLLECTION_NAME,
    SCHEDULE_GROUPS_STATS,
    SCHEDULE_UPDATES_COLLECTION,
)
from app.models.schedule import (
    GroupStatsModel,
    LessonModel,
    RoomLessonModel,
    RoomScheduleModel,
    ScheduleByWeekdaysModel,
    ScheduleModel,
    ScheduleUpdateModel,
    TeacherLessonModel,
    TeacherSchedulesModelResponse,
)

WEEKDAYS = (
    (1, "monday"),
    (2, "tuesday"),
    (3, "wednesday"),
    (4, "thursday"),
    (5, "friday"),
    (6, "saturday"),
)


def _numeric_schedule(document: dict[str, Any]) -> dict[str, Any]:
    return {str(number): document["schedule"][weekday] for number, weekday in WEEKDAYS}


def _nested_text_query(field: str, value: str) -> dict[str, object]:
    escaped_value = re.escape(value.strip())
    return {
        "$or": [
            {
                f"schedule.{weekday}.lessons": {
                    "$elemMatch": {
                        "$elemMatch": {field: {"$regex": escaped_value, "$options": "i"}}
                    }
                }
            }
            for _, weekday in WEEKDAYS
        ]
    }


def _lessons(document: dict[str, Any]) -> Iterator[tuple[int, int, dict[str, Any]]]:
    for weekday_number, weekday in WEEKDAYS:
        day = document["schedule"].get(weekday, {})
        for lesson_number, slot in enumerate(day.get("lessons", [])):
            for lesson in slot:
                yield weekday_number, lesson_number, lesson


async def save_schedule(
    conn: AsyncMongoClient,
    group: str,
    schedule: ScheduleByWeekdaysModel,
) -> None:
    await conn[DATABASE_NAME][SCHEDULE_COLLECTION_NAME].replace_one(
        {"group": group},
        {"group": group, "schedule": schedule.model_dump()},
        upsert=True,
    )


async def get_full_schedule(
    conn: AsyncMongoClient,
    group_name: str,
) -> ScheduleModel | None:
    """Return the full schedule for one group."""

    schedule = await conn[DATABASE_NAME][SCHEDULE_COLLECTION_NAME].find_one(
        {"group": group_name}, {"_id": 0}
    )
    if schedule is None:
        return None
    return ScheduleModel(
        group=schedule["group"],
        schedule=_numeric_schedule(schedule),
    )


async def get_groups(conn: AsyncMongoClient) -> list[str]:
    """Return all groups with a cached schedule."""

    cursor = conn[DATABASE_NAME][SCHEDULE_COLLECTION_NAME].find({}, {"group": 1, "_id": 0})
    documents = await cursor.to_list(None)
    return sorted(document["group"] for document in documents)


async def find_teacher(
    conn: AsyncMongoClient,
    teacher_name: str,
) -> TeacherSchedulesModelResponse | None:
    normalized_name = teacher_name.strip().casefold()
    cursor = conn[DATABASE_NAME][SCHEDULE_COLLECTION_NAME].find(
        _nested_text_query("teachers", teacher_name),
        {"_id": 0},
    )
    schedules = await cursor.to_list(None)

    result = []
    for schedule in schedules:
        for weekday, lesson_number, lesson in _lessons(schedule):
            if any(normalized_name in teacher.casefold() for teacher in lesson.get("teachers", [])):
                result.append(
                    TeacherLessonModel(
                        group=schedule["group"],
                        weekday=weekday,
                        lesson_number=lesson_number,
                        lesson=LessonModel(**lesson),
                    )
                )

    if not result:
        return None
    return TeacherSchedulesModelResponse(schedules=result)


async def find_room(
    conn: AsyncMongoClient,
    room_name: str,
) -> RoomScheduleModel | None:
    normalized_name = room_name.strip().casefold()
    cursor = conn[DATABASE_NAME][SCHEDULE_COLLECTION_NAME].find(
        _nested_text_query("rooms", room_name),
        {"_id": 0},
    )
    schedules = await cursor.to_list(None)

    result = []
    for schedule in schedules:
        for weekday, lesson_number, lesson in _lessons(schedule):
            matching_room = next(
                (room for room in lesson.get("rooms", []) if normalized_name in room.casefold()),
                None,
            )
            if matching_room is not None:
                result.append(
                    RoomLessonModel(
                        group=schedule["group"],
                        room=matching_room,
                        weekday=weekday,
                        lesson_number=lesson_number,
                        lesson=LessonModel(**lesson),
                    )
                )

    if not result:
        return None
    return RoomScheduleModel(schedules=result)


async def update_schedule_updates(
    conn: AsyncMongoClient,
    updates: list[ScheduleUpdateModel],
) -> None:
    collection = conn[DATABASE_NAME][SCHEDULE_UPDATES_COLLECTION]
    for update in updates:
        update_in_db = await collection.find_one({"groups": {"$in": update.groups}})
        if update_in_db:
            await collection.update_one(
                {"_id": update_in_db["_id"]},
                {"$set": update.model_dump()},
            )
        else:
            await collection.insert_one(update.model_dump())


async def get_all_schedule_updates(
    conn: AsyncMongoClient,
) -> list[ScheduleUpdateModel]:
    cursor = conn[DATABASE_NAME][SCHEDULE_UPDATES_COLLECTION].find({}, {"_id": 0})
    updates = await cursor.to_list(None)
    return [ScheduleUpdateModel(**update) for update in updates]


async def get_schedule_update_by_group(
    conn: AsyncMongoClient,
    group: str,
) -> ScheduleUpdateModel | None:
    update = await conn[DATABASE_NAME][SCHEDULE_UPDATES_COLLECTION].find_one(
        {"groups": group},
        {"_id": 0},
    )
    return ScheduleUpdateModel(**update) if update else None


async def update_group_stats(conn: AsyncMongoClient, group: str) -> None:
    await conn[DATABASE_NAME][SCHEDULE_GROUPS_STATS].update_one(
        {"group": group},
        {"$inc": {"received": 1}},
        upsert=True,
    )


async def get_groups_stats(conn: AsyncMongoClient) -> list[GroupStatsModel]:
    cursor = conn[DATABASE_NAME][SCHEDULE_GROUPS_STATS].find({}, {"_id": 0})
    groups_stats = await cursor.to_list(None)
    return [GroupStatsModel(**stats) for stats in groups_stats]
