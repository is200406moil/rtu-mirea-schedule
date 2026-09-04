import datetime
from typing import Any

from app.crud import schedule as schedule_crud
from app.models.schedule import ScheduleUpdateModel


def _schedule_document() -> dict[str, Any]:
    empty_day = {"lessons": []}
    return {
        "group": "ИКБО-14-23",
        "schedule": {
            "monday": {
                "lessons": [
                    [
                        {
                            "name": "Алгоритмы",
                            "weeks": [1, 2],
                            "time_start": "09:00",
                            "time_end": "10:30",
                            "types": "Лекция",
                            "teachers": ["Иванов И. И."],
                            "rooms": ["А-101"],
                        }
                    ]
                ]
            },
            "tuesday": empty_day,
            "wednesday": empty_day,
            "thursday": empty_day,
            "friday": empty_day,
            "saturday": empty_day,
        },
    }


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    async def to_list(self, _: int | None) -> list[dict[str, Any]]:
        return self.documents


class FakeCollection:
    def __init__(self, documents: list[dict[str, Any]] | None = None) -> None:
        self.documents = documents or []
        self.last_query: dict[str, Any] | None = None
        self.updated: dict[str, Any] | None = None
        self.inserted: dict[str, Any] | None = None

    def find(self, query: dict[str, Any], _: dict[str, int]) -> FakeCursor:
        self.last_query = query
        return FakeCursor(self.documents)

    async def find_one(
        self,
        query: dict[str, Any],
        _: dict[str, int] | None = None,
    ) -> dict[str, Any] | None:
        self.last_query = query
        return self.documents[0] if self.documents else None

    async def update_one(self, _: dict[str, Any], update: dict[str, Any]) -> None:
        self.updated = update

    async def insert_one(self, document: dict[str, Any]) -> None:
        self.inserted = document


class FakeDatabase:
    def __init__(self, collection: FakeCollection) -> None:
        self.collection = collection

    def __getitem__(self, _: str) -> FakeCollection:
        return self.collection


class FakeClient:
    def __init__(self, collection: FakeCollection) -> None:
        self.database = FakeDatabase(collection)

    def __getitem__(self, _: str) -> FakeDatabase:
        return self.database


async def test_teacher_and_room_search_return_matching_lessons() -> None:
    collection = FakeCollection([_schedule_document()])
    client = FakeClient(collection)

    teacher = await schedule_crud.find_teacher(client, "иванов")
    room = await schedule_crud.find_room(client, "а-101")

    assert teacher is not None
    assert teacher.schedules[0].lesson.name == "Алгоритмы"
    assert room is not None
    assert room.schedules[0].room == "А-101"


async def test_search_treats_regex_characters_as_plain_text() -> None:
    collection = FakeCollection([_schedule_document()])
    client = FakeClient(collection)

    result = await schedule_crud.find_teacher(client, ".*")

    assert result is None
    assert collection.last_query is not None
    monday_filter = collection.last_query["$or"][0]
    regex = monday_filter["schedule.monday.lessons"]["$elemMatch"]["$elemMatch"]["teachers"][
        "$regex"
    ]
    assert regex == r"\.\*"


async def test_group_update_queries_use_exact_array_values() -> None:
    collection = FakeCollection()
    client = FakeClient(collection)
    update = ScheduleUpdateModel(
        groups=["ИКБО-14-23"],
        updated_at=datetime.datetime(2026, 9, 4, tzinfo=datetime.UTC),
    )

    await schedule_crud.update_schedule_updates(client, [update])

    assert collection.last_query == {"groups": {"$in": ["ИКБО-14-23"]}}
    assert collection.inserted == update.model_dump()


async def test_groups_are_always_returned_as_a_sorted_list() -> None:
    collection = FakeCollection([{"group": "Б"}, {"group": "А"}])
    client = FakeClient(collection)

    assert await schedule_crud.get_groups(client) == ["А", "Б"]

    collection.documents = []
    assert await schedule_crud.get_groups(client) == []
