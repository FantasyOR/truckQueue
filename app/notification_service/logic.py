from __future__ import annotations

import logging
from datetime import timedelta

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, BookingStatus, Notification, Driver
from app.queue_logic import recalc_queue
from app.utils.time_utils import now_tz


NOTIF_CONFIRMED = "CONFIRMED"
NOTIF_REMINDER_24H = "REMINDER_24H"
NOTIF_REMINDER_1H = "REMINDER_1H"
NOTIF_QUEUE_POSITION = "QUEUE_POSITION_CHANGED"


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


async def process_notifications(session: Session, bot: Bot) -> None:
    now = now_tz()

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

        # Confirmation
        if not _already_sent(session, booking.id, NOTIF_CONFIRMED):
            await send_notification(
                bot,
                driver.telegram_user_id,
                f"Бронирование подтверждено: {booking.date} {booking.slot_start.strftime('%H:%M')} элеватор {booking.elevator.name}",
            )
            session.add(Notification(booking_id=booking.id, notification_type=NOTIF_CONFIRMED))

        # Reminder 24h
        if (
            booking.slot_start - now <= timedelta(hours=24)
            and booking.slot_start > now
            and not _already_sent(session, booking.id, NOTIF_REMINDER_24H)
        ):
            await send_notification(
                bot,
                driver.telegram_user_id,
                f"Напоминание: завтра {booking.date} в {booking.slot_start.strftime('%H:%M')} элеватор {booking.elevator.name}",
            )
            session.add(Notification(booking_id=booking.id, notification_type=NOTIF_REMINDER_24H))

        # Reminder 1h
        if (
            booking.slot_start - now <= timedelta(hours=1)
            and booking.slot_start > now
            and not _already_sent(session, booking.id, NOTIF_REMINDER_1H)
        ):
            await send_notification(
                bot,
                driver.telegram_user_id,
                f"Напоминание: через час слот {booking.slot_start.strftime('%H:%M')} на элеваторе {booking.elevator.name}",
            )
            session.add(Notification(booking_id=booking.id, notification_type=NOTIF_REMINDER_1H))

        # Queue position change
        if booking.last_notified_queue_index != booking.queue_index:
            await send_notification(
                bot,
                driver.telegram_user_id,
                f"Ваша позиция в очереди изменилась: теперь {booking.queue_index}",
            )
            booking.last_notified_queue_index = booking.queue_index
            session.add(Notification(booking_id=booking.id, notification_type=NOTIF_QUEUE_POSITION))

    session.commit()
