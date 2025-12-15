from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

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
    if booking.status == BookingStatus.UNLOADED:
        return None

    rows: list[list[InlineKeyboardButton]] = []
    action_row: list[InlineKeyboardButton] = []
    show_arrive = booking.status not in (
        BookingStatus.ARRIVED,
        BookingStatus.UNLOADED,
        BookingStatus.CANCELLED,
    )
    show_unload = booking.status in (BookingStatus.ARRIVED,)

    if show_arrive:
        action_row.append(
            InlineKeyboardButton(text="Прибыл", callback_data=f"arrive:{booking.id}")
        )
    if show_unload and "unload" not in disabled:
        action_row.append(
            InlineKeyboardButton(text="Разгрузился", callback_data=f"unload:{booking.id}")
        )
    if action_row:
        rows.append(action_row)
    if "cancel" not in disabled and not show_unload:
        rows.append(
            [InlineKeyboardButton(text="Отменить", callback_data=f"cancel:{booking.id}")]
        )
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def elevators_keyboard(elevators: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"elevator:{name}")]
        for name in elevators
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="Сегодня"), KeyboardButton(text="Завтра")],
        [KeyboardButton(text="Сменить элеватор")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
