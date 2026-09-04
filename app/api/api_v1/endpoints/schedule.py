import asyncio
import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Path, status
from pymongo import AsyncMongoClient
from starlette.status import HTTP_404_NOT_FOUND

from app.core.config import SECRET_REFRESH_KEY
from app.core.schedule_utils import ScheduleUtils
from app.crud.schedule import (
    find_room,
    find_teacher,
    get_full_schedule,
    get_groups,
    get_groups_stats,
    update_group_stats,
)
from app.database.database import get_database
from app.models.schedule import (
    GroupsListResponse,
    GroupStatsModel,
    RoomScheduleModel,
    ScheduleModel,
    TeacherSchedulesModelResponse,
    WeekModelResponse,
)
from app.schedule_parser.ical import parse_schedule

router = APIRouter()
logger = logging.getLogger(__name__)
_refresh_task: asyncio.Task[None] | None = None
_refresh_status: dict[str, str] = {"state": "idle", "message": "Refresh was not started yet"}


def _authorize_refresh(refresh_key: str | None) -> None:
    if not SECRET_REFRESH_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Schedule refresh is not configured",
        )
    if refresh_key is None or not secrets.compare_digest(refresh_key, SECRET_REFRESH_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh key",
        )


async def _run_refresh(db: AsyncMongoClient) -> None:
    global _refresh_status

    _refresh_status = {"state": "running", "message": "Refresh in progress"}
    try:
        saved = await parse_schedule(db)
        _refresh_status = {
            "state": "ok",
            "message": f"Refresh completed: {saved} groups saved",
        }
    except Exception:
        logger.exception("Refresh failed")
        _refresh_status = {
            "state": "failed",
            "message": "Refresh failed; check application logs",
        }


@router.post(
    "/refresh",
    status_code=status.HTTP_202_ACCEPTED,
    description="Start an asynchronous schedule refresh",
)
async def refresh(
    db: AsyncMongoClient = Depends(get_database),
    refresh_key: str | None = Header(default=None, alias="X-Refresh-Key"),
) -> dict[str, object]:
    global _refresh_task, _refresh_status

    _authorize_refresh(refresh_key)

    if _refresh_task and not _refresh_task.done():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Schedule refresh is already running",
        )

    _refresh_status = {"state": "running", "message": "Refresh in progress"}
    _refresh_task = asyncio.create_task(_run_refresh(db))
    return {"status": "started", "detail": _refresh_status}


@router.get(
    "/refresh/status",
    description="Get current refresh status",
)
async def refresh_status(
    refresh_key: str | None = Header(default=None, alias="X-Refresh-Key"),
) -> dict[str, object]:
    _authorize_refresh(refresh_key)

    running = bool(_refresh_task and not _refresh_task.done())
    return {"running": running, "detail": _refresh_status}


@router.get(
    "/schedule/{group}/full_schedule",
    response_description="Return full schedule of one group",
    response_model=ScheduleModel,
)
async def full_schedule(
    group: str = Path(..., min_length=10),
    db: AsyncMongoClient = Depends(get_database),
):
    schedule = await get_full_schedule(db, group)

    if not schedule:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Schedule for group '{group}' not found",
        )

    await update_group_stats(db, group)

    return schedule


@router.get(
    "/schedule/groups",
    response_description="List of all groups",
    response_model=GroupsListResponse,
)
async def groups_list(db: AsyncMongoClient = Depends(get_database)):
    groups = await get_groups(db)

    if not groups:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="Groups not found",
        )

    return GroupsListResponse(groups=groups, count=len(groups))


@router.get(
    "/schedule/current_week",
    response_description="Get current week",
    response_model=WeekModelResponse,
)
async def current_week():
    return WeekModelResponse(week=ScheduleUtils.get_week(ScheduleUtils.now_date()))


@router.get(
    "/schedule/teacher/{teacher_name}",
    response_description="Find teacher schedule by teacher name",
    response_model=TeacherSchedulesModelResponse,
)
async def teacher_schedule(
    teacher_name: str = Path(..., min_length=2, max_length=120),
    db: AsyncMongoClient = Depends(get_database),
):
    schedule = await find_teacher(db, teacher_name)

    if not schedule:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Teacher with name {teacher_name} not found",
        )

    return schedule


@router.get(
    "/schedule/room/{room_name}",
    response_description="Find room schedule by room name",
    response_model=RoomScheduleModel,
)
async def room_schedule(
    room_name: str = Path(..., min_length=1, max_length=120),
    db: AsyncMongoClient = Depends(get_database),
):
    schedule = await find_room(db, room_name)

    if not schedule:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"Room with name {room_name} not found",
        )

    return schedule


@router.get(
    "/schedule/groups_stats/",
    response_description="Get statistics of requests to group schedules",
    response_model=list[GroupStatsModel],
)
async def groups_stats(db: AsyncMongoClient = Depends(get_database)):
    stats = await get_groups_stats(db)

    if not stats:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="Stats not found")

    return stats
