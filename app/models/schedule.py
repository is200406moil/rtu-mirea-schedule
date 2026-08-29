import datetime

from pydantic import BaseModel, ConfigDict, Field


class WeekModelResponse(BaseModel):
    week: int


class GroupsListResponse(BaseModel):
    count: int
    groups: list[str]


class LessonModel(BaseModel):
    name: str
    weeks: list[int]
    time_start: str
    time_end: str
    types: str
    teachers: list[str]
    rooms: list[str]


class ScheduleLessonsModel(BaseModel):
    lessons: list[list[LessonModel]]


class ScheduleByWeekdaysModelResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    monday: ScheduleLessonsModel = Field(..., alias="1", title="monday")
    tuesday: ScheduleLessonsModel = Field(..., alias="2", title="tuesday")
    wednesday: ScheduleLessonsModel = Field(..., alias="3", title="wednesday")
    thursday: ScheduleLessonsModel = Field(..., alias="4", title="thursday")
    friday: ScheduleLessonsModel = Field(..., alias="5", title="friday")
    saturday: ScheduleLessonsModel = Field(..., alias="6", title="saturday")


class ScheduleByWeekdaysModel(BaseModel):
    monday: ScheduleLessonsModel
    tuesday: ScheduleLessonsModel
    wednesday: ScheduleLessonsModel
    thursday: ScheduleLessonsModel
    friday: ScheduleLessonsModel
    saturday: ScheduleLessonsModel


class ScheduleModel(BaseModel):
    group: str
    schedule: ScheduleByWeekdaysModelResponse


class TeacherLessonModel(BaseModel):
    group: str
    weekday: int
    lesson_number: int
    lesson: LessonModel


class RoomLessonModel(BaseModel):
    group: str
    room: str
    weekday: int
    lesson_number: int
    lesson: LessonModel


class RoomScheduleModel(BaseModel):
    schedules: list[RoomLessonModel]


class TeacherSchedulesModelResponse(BaseModel):
    schedules: list[TeacherLessonModel]


class ScheduleUpdateModel(BaseModel):
    groups: list[str]
    updated_at: datetime.datetime


class GroupStatsModel(BaseModel):
    group: str
    received: int
