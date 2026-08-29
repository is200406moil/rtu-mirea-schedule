import datetime
from types import SimpleNamespace

import requests

from app.core.schedule_utils import MOSCOW_TZ, ScheduleUtils
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
