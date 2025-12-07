from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import settings


def get_timezone() -> ZoneInfo:
    return ZoneInfo(settings.default_timezone)


def now_tz() -> datetime:
    return datetime.now(tz=get_timezone())


def combine_date_time(day: date, t: time) -> datetime:
    tz = get_timezone()
    if t.tzinfo is None:
        t = time(t.hour, t.minute, t.second, t.microsecond, tzinfo=tz)
    return datetime.combine(day, t).astimezone(tz)


def build_daily_slots(work_day_start: time, work_day_end: time, bookable_slots_per_day: int) -> list[tuple[time, time]]:
    duration = timedelta(minutes=settings.slot_duration_minutes)
    slots: list[tuple[time, time]] = []
    tz = work_day_start.tzinfo or get_timezone()
    current = datetime.combine(date.today(), work_day_start, tzinfo=tz)
    end_dt = datetime.combine(date.today(), work_day_end, tzinfo=tz)
    while current + duration <= end_dt and len(slots) < bookable_slots_per_day:
        slot_end = current + duration
        slots.append((current.timetz(), slot_end.timetz()))
        current = slot_end
    return slots


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()
