import asyncio
import datetime
import logging
import re
from collections import defaultdict
from itertools import groupby
from typing import Any

import requests
from pymongo import AsyncMongoClient

from ..core.schedule_utils import ScheduleUtils
from ..crud.schedule import save_schedule
from ..models.schedule import LessonModel, ScheduleByWeekdaysModel, ScheduleLessonsModel

logger = logging.getLogger(__name__)

SCHEDULE_OF_BASE_URL = "https://schedule-of.mirea.ru"
SEARCH_URL = f"{SCHEDULE_OF_BASE_URL}/schedule/api/search"
ICAL_URL_TEMPLATE = (
    f"{SCHEDULE_OF_BASE_URL}/schedule/api/ical/{{schedule_target}}/{{group_id}}?includeMeta=true"
)
GROUP_NAME_RE = re.compile(r"^[А-ЯA-ZЁ]{2,6}-\d{2}-\d{2}$")
REQUEST_HEADERS = {"User-Agent": "rtu-mirea-schedule-bot/1.0"}


async def _request(
    client: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = 20,
    retries: int = 5,
) -> requests.Response:
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = await asyncio.to_thread(
                client.get,
                url,
                params=params,
                timeout=timeout,
                headers=REQUEST_HEADERS,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            last_error = error
            if attempt < retries:
                await asyncio.sleep(min(2.0, 0.25 * attempt))
                continue
            break

    raise RuntimeError(f"Request failed for {url}: {last_error}")


def _unfold_ical_lines(raw_ical: str) -> list[str]:
    lines = raw_ical.splitlines()
    unfolded: list[str] = []

    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    return unfolded


def _parse_ical_datetime(value: str):
    if "T" in value:
        value = value.rstrip("Z")
        return datetime.datetime.strptime(value, "%Y%m%dT%H%M%S")
    return datetime.datetime.strptime(value, "%Y%m%d")


def _extract_field(line: str) -> tuple[str, str]:
    key, value = line.split(":", 1)
    return key, value.strip()


def _lesson_weeks(dt_start: datetime.datetime, rrule: str) -> list[int]:
    if "INTERVAL=2" not in rrule:
        return [1, 2]

    week_number = ScheduleUtils.get_week(dt_start)
    return [1] if week_number % 2 else [2]


async def _extract_group_items(client: requests.Session) -> list[dict[str, Any]]:
    page_token = None
    groups: dict[str, dict[str, Any]] = {}

    for _ in range(500):
        params = {"limit": 100, "match": "-"}
        if page_token:
            params["pageToken"] = page_token

        try:
            payload = (await _request(client, SEARCH_URL, params=params, timeout=20)).json()
        except Exception as error:
            logger.error("Failed to read search page token=%s: %s", page_token, error)
            break

        for item in payload.get("data", []):
            title = item.get("targetTitle", "")
            if item.get("scheduleTarget") == 1 and GROUP_NAME_RE.fullmatch(title):
                groups[title] = item

        page_token = payload.get("nextPageToken")
        if not page_token:
            break

        # Avoid aggressive request bursts that can trigger upstream disconnects.
        await asyncio.sleep(0.05)

    result = list(groups.values())
    logger.info("Discovered %s groups in schedule-of API", len(result))
    return result


async def _parse_group_ical(
    client: requests.Session,
    schedule_target: int,
    group_id: int,
) -> ScheduleByWeekdaysModel:
    response = await _request(
        client,
        ICAL_URL_TEMPLATE.format(schedule_target=schedule_target, group_id=group_id),
        timeout=30,
    )

    lines = _unfold_ical_lines(response.text)
    lessons_by_weekdays = defaultdict(list)

    in_event = False
    event_lines: list[str] = []
    for line in lines:
        if line == "BEGIN:VEVENT":
            in_event = True
            event_lines = []
            continue

        if line == "END:VEVENT":
            in_event = False
            event = {}
            for event_line in event_lines:
                if ":" not in event_line:
                    continue
                key, value = _extract_field(event_line)
                event[key] = value

            dtstart_raw = next((v for k, v in event.items() if k.startswith("DTSTART")), None)
            dtend_raw = next((v for k, v in event.items() if k.startswith("DTEND")), None)
            if not dtstart_raw or not dtend_raw:
                continue

            dt_start = _parse_ical_datetime(dtstart_raw)
            dt_end = _parse_ical_datetime(dtend_raw)
            if dt_start.hour == 0 and dt_end.hour == 0:
                continue

            weekday = dt_start.isoweekday()
            if weekday > 6:
                continue

            discipline = event.get("X-META-DISCIPLINE", "").strip()
            lesson_type = event.get("X-META-LESSON_TYPE", "").strip()
            if not discipline:
                summary = event.get("SUMMARY", "").strip()
                if " " in summary:
                    lesson_type, discipline = summary.split(" ", 1)
                else:
                    discipline = summary

            teacher = event.get("X-META-TEACHER", "").strip()
            teachers = [teacher] if teacher else []

            room = event.get("X-META-AUDITORIUM", "").strip() or event.get("LOCATION", "").strip()
            rooms = [room] if room else []

            time_start = dt_start.strftime("%H:%M")
            time_end = dt_end.strftime("%H:%M")
            lesson_number = f"{time_start}-{time_end}"

            lesson = LessonModel(
                name=discipline,
                weeks=_lesson_weeks(dt_start, event.get("RRULE", "")),
                time_start=time_start,
                time_end=time_end,
                types=lesson_type,
                teachers=teachers,
                rooms=rooms,
            )

            lessons_by_weekdays[str(weekday)].append((lesson_number, lesson))
            continue

        if in_event:
            event_lines.append(line)

    by_day_models = {}
    for weekday in ["1", "2", "3", "4", "5", "6"]:
        day_lessons = lessons_by_weekdays.get(weekday, [])
        grouped = []
        if day_lessons:
            day_lessons = sorted(day_lessons, key=lambda item: item[0])
            grouped = [list(g) for _, g in groupby(day_lessons, key=lambda item: item[0])]

        by_day_models[weekday] = ScheduleLessonsModel(
            lessons=[[lesson for _, lesson in slot] for slot in grouped]
        )

    return ScheduleByWeekdaysModel(
        monday=by_day_models["1"],
        tuesday=by_day_models["2"],
        wednesday=by_day_models["3"],
        thursday=by_day_models["4"],
        friday=by_day_models["5"],
        saturday=by_day_models["6"],
    )


async def parse_schedule(conn: AsyncMongoClient) -> int:
    """Parse schedule-of API and save parsed group schedules to database."""

    client = requests.Session()
    try:
        groups = await _extract_group_items(client)
        if not groups:
            raise RuntimeError("No groups were discovered in schedule-of API")

        saved = 0
        for group in groups:
            group_name = group.get("targetTitle", "")
            group_id = group.get("id")
            schedule_target = group.get("scheduleTarget")

            if not group_name or group_id is None or schedule_target is None:
                continue

            try:
                by_weekdays = await _parse_group_ical(client, schedule_target, group_id)
                await save_schedule(conn, group_name, by_weekdays)
                saved += 1
            except Exception as error:
                logger.error("Failed to parse %s: %s", group_name, error)

            await asyncio.sleep(0.02)
    finally:
        client.close()

    logger.info("Saved schedules for %s groups", saved)
    return saved
