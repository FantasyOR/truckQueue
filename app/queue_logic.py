from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, BookingStatus


def recalc_queue(session: Session, elevator_id: int, booking_date: date) -> list[Booking]:
    stmt = (
        select(Booking)
        .where(
            Booking.elevator_id == elevator_id,
            Booking.date == booking_date,
            Booking.status != BookingStatus.CANCELLED,
        )
        .order_by(Booking.slot_start, Booking.created_at, Booking.id)
    )
    bookings = list(session.scalars(stmt).all())
    for idx, booking in enumerate(bookings):
        booking.queue_index = idx

    # Late swap: if first has not arrived but second has arrived — swap their queue positions
    if len(bookings) >= 2:
        first, second = bookings[0], bookings[1]
        if first.arrived_at is None and second.arrived_at is not None:
            first.queue_index, second.queue_index = 1, 0
            bookings[0], bookings[1] = second, first

    session.flush()
    return bookings
