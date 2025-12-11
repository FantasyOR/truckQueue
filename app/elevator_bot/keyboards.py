from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.models import Booking, BookingStatus


def booking_actions_keyboard(booking: Booking) -> InlineKeyboardMarkup | None:
    disabled: set[str] = set()
    if booking.status in (
        BookingStatus.ARRIVED,
        BookingStatus.UNLOADED,
        BookingStatus.CANCELLED,
    ):
        disabled.add("arrive")
    if booking.status in (BookingStatus.UNLOADED, BookingStatus.CANCELLED):
        disabled.add("unload")
    if booking.status == BookingStatus.CANCELLED:
        disabled.add("cancel")

    rows: list[list[InlineKeyboardButton]] = []
    action_row: list[InlineKeyboardButton] = []
    if "arrive" not in disabled:
        action_row.append(
            InlineKeyboardButton(text="Прибыл", callback_data=f"arrive:{booking.id}")
        )
    if "unload" not in disabled:
        action_row.append(
            InlineKeyboardButton(text="Разгрузка", callback_data=f"unload:{booking.id}")
        )
    if action_row:
        rows.append(action_row)
    if "cancel" not in disabled:
        rows.append(
            [InlineKeyboardButton(text="Отменить", callback_data=f"cancel:{booking.id}")]
        )
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def elevators_keyboard(elevators: list[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=name, callback_data=f"elevator:{name}") for name in elevators]]
    )
