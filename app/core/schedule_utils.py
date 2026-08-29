import datetime
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


class ScheduleUtils:
    @staticmethod
    def get_week(value: datetime.datetime | None = None) -> int:
        """Return the one-based academic week number for a date."""

        current = ScheduleUtils.now_date() if value is None else value
        if current.tzinfo is None:
            current = current.replace(tzinfo=MOSCOW_TZ)

        semester_start = ScheduleUtils.get_semester_start(current)
        first_monday = semester_start - datetime.timedelta(days=semester_start.weekday())
        return max(1, (current.date() - first_monday.date()).days // 7 + 1)

    @staticmethod
    def get_semester_start(value: datetime.datetime | None = None) -> datetime.datetime:
        current = ScheduleUtils.now_date() if value is None else value
        if current.month >= 9:
            return datetime.datetime(current.year, 9, 1, tzinfo=MOSCOW_TZ)
        return datetime.datetime(current.year, 2, 9, tzinfo=MOSCOW_TZ)

    @staticmethod
    def now_date() -> datetime.datetime:
        return datetime.datetime.now(MOSCOW_TZ)
