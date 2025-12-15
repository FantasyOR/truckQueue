from __future__ import annotations

import logging
from datetime import timedelta

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Booking, BookingStatus, Notification, Driver
from app.queue_logic import recalc_queue
from app.utils.time_utils import now_tz, get_timezone


async def send_notification(bot: Bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:  # pragma: no cover - network error logging
        logging.exception("Failed to send notification: %s", e)


def _already_sent(session: Session, booking_id: int, notif_type: str) -> bool:
    stmt = select(Notification).where(
        Notification.booking_id == booking_id,
        Notification.notification_type == notif_type,
    )
    return session.scalars(stmt).first() is not None


def _notif_type_for_offset(minutes: int) -> str:
    return f"REMINDER_{minutes}M"


def _human_offset(minutes: int) -> str:
    if minutes >= 60 and minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} ч"
    return f"{minutes} мин"


async def process_notifications(session: Session, bot: Bot) -> None:
    now = now_tz()
    tz = get_timezone()
    offsets = sorted({m for m in settings.notification_offsets_minutes if m > 0})

    # Recalculate queues for all active days/elevators
    pairs = (
        session.query(Booking.elevator_id, Booking.date)
        .filter(Booking.status != BookingStatus.CANCELLED)
        .distinct()
        .all()
    )
    for elevator_id, booking_date in pairs:
        recalc_queue(session, elevator_id, booking_date)
    session.commit()

    bookings = (
        session.query(Booking)
        .join(Driver)
        .filter(Booking.status != BookingStatus.CANCELLED)
        .all()
    )

    for booking in bookings:
        driver = booking.driver
        if driver is None:
            continue
        slot_start = booking.slot_start
        if slot_start.tzinfo is None:
            slot_start = slot_start.replace(tzinfo=tz)
        else:
            slot_start = slot_start.astimezone(tz)
        booking.slot_start = slot_start
        session.add(booking)

        delta = slot_start - now
        if delta <= timedelta(0):
            continue

        due_offsets: list[int] = []
        for minutes in offsets:
            threshold = timedelta(minutes=minutes)
            notif_type = _notif_type_for_offset(minutes)
            if delta <= threshold and not _already_sent(session, booking.id, notif_type):
                due_offsets.append(minutes)
        if due_offsets:
            minutes = min(due_offsets)  # отправляем только самое близкое по времени
            notif_type = _notif_type_for_offset(minutes)
            human_delta = _human_offset(minutes)
            await send_notification(
                bot,
                driver.telegram_user_id,
                f"Напоминание: слот {slot_start.strftime('%d.%m %H:%M')} на элеваторе {booking.elevator.name} через ≈{human_delta}.",
            )
            session.add(
                Notification(booking_id=booking.id, notification_type=notif_type)
            )

    session.commit()
