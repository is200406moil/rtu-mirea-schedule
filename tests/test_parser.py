import datetime
from types import SimpleNamespace

import pytest
import requests

from app.core.schedule_utils import MOSCOW_TZ, ScheduleUtils
from app.models.schedule import ScheduleByWeekdaysModel, ScheduleLessonsModel
from app.schedule_parser import ical


def test_academic_week_is_counted_from_monday() -> None:
    assert ScheduleUtils.get_week(datetime.datetime(2026, 9, 1, tzinfo=MOSCOW_TZ)) == 1
    assert ScheduleUtils.get_week(datetime.datetime(2026, 9, 7, tzinfo=MOSCOW_TZ)) == 2


async def test_parse_group_ical(monkeypatch) -> None:
    ical_text = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260907T090000
DTEND:20260907T103000
RRULE:FREQ=WEEKLY;INTERVAL=2
X-META-DISCIPLINE:Алгоритмы и структуры данных
X-META-LESSON_TYPE:Лекция
X-META-TEACHER:Иванов И. И.
X-META-AUDITORIUM:А-101
END:VEVENT
END:VCALENDAR
    """

    async def fake_request(*args, **kwargs):
        return SimpleNamespace(text=ical_text)

    monkeypatch.setattr(ical, "_request", fake_request)

    with requests.Session() as client:
        schedule = await ical._parse_group_ical(client, schedule_target=1, group_id=42)

    lesson = schedule.monday.lessons[0][0]
    assert lesson.name == "Алгоритмы и структуры данных"
    assert lesson.weeks == [2]
    assert lesson.teachers == ["Иванов И. И."]
    assert lesson.rooms == ["А-101"]


def _empty_schedule() -> ScheduleByWeekdaysModel:
    return ScheduleByWeekdaysModel(
        monday=ScheduleLessonsModel(lessons=[]),
        tuesday=ScheduleLessonsModel(lessons=[]),
        wednesday=ScheduleLessonsModel(lessons=[]),
        thursday=ScheduleLessonsModel(lessons=[]),
        friday=ScheduleLessonsModel(lessons=[]),
        saturday=ScheduleLessonsModel(lessons=[]),
    )


async def test_refresh_publishes_only_after_every_group_is_parsed(monkeypatch) -> None:
    groups = [
        {"targetTitle": "ИКБО-14-23", "id": 1, "scheduleTarget": 1},
        {"targetTitle": "ИКБО-15-23", "id": 2, "scheduleTarget": 1},
    ]
    published = {}

    async def fake_extract_group_items(_):
        return groups

    async def fake_parse_group_ical(_, schedule_target, group_id):
        assert schedule_target == 1
        assert group_id in {1, 2}
        return _empty_schedule()

    async def fake_replace_all_schedules(_, schedules):
        published.update(schedules)

    monkeypatch.setattr(ical, "_extract_group_items", fake_extract_group_items)
    monkeypatch.setattr(ical, "_parse_group_ical", fake_parse_group_ical)
    monkeypatch.setattr(ical, "replace_all_schedules", fake_replace_all_schedules)

    saved = await ical.parse_schedule(object())

    assert saved == 2
    assert set(published) == {"ИКБО-14-23", "ИКБО-15-23"}


async def test_refresh_keeps_current_dataset_if_any_group_fails(monkeypatch) -> None:
    groups = [
        {"targetTitle": "ИКБО-14-23", "id": 1, "scheduleTarget": 1},
        {"targetTitle": "ИКБО-15-23", "id": 2, "scheduleTarget": 1},
    ]
    publish_called = False

    async def fake_extract_group_items(_):
        return groups

    async def fake_parse_group_ical(_, _schedule_target, group_id):
        if group_id == 2:
            raise RuntimeError("upstream error")
        return _empty_schedule()

    async def fake_replace_all_schedules(_, _schedules):
        nonlocal publish_called
        publish_called = True

    monkeypatch.setattr(ical, "_extract_group_items", fake_extract_group_items)
    monkeypatch.setattr(ical, "_parse_group_ical", fake_parse_group_ical)
    monkeypatch.setattr(ical, "replace_all_schedules", fake_replace_all_schedules)

    with pytest.raises(ical.ScheduleRefreshError, match="1 of 2 groups"):
        await ical.parse_schedule(object())

    assert publish_called is False
