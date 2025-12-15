from datetime import date, timedelta

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.models import Elevator


def elevators_keyboard(elevators: list[Elevator]) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text=e.name)] for e in elevators]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def dates_keyboard() -> ReplyKeyboardMarkup:
    today = date.today()
    tomorrow = today + timedelta(days=1)
    buttons = [
        [KeyboardButton(text=today.isoformat())],
        [KeyboardButton(text=tomorrow.isoformat())],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def slots_keyboard(slots: list[str]) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text=s)] for s in slots]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def confirmation_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="Подтвердить")],
        [KeyboardButton(text="Отмена")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [
            KeyboardButton(text="Записаться"),
            KeyboardButton(text="Мои бронирования"),
        ],
        [KeyboardButton(text="Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def inline_offer_keyboard(booking_id: int, fallback_id: int | None) -> InlineKeyboardMarkup:
    data_yes = f"come:yes:{booking_id}"
    data_no = f"come:no:{booking_id}:{fallback_id or 0}"
    buttons = [
        [
            InlineKeyboardButton(text="Да, еду", callback_data=data_yes),
            InlineKeyboardButton(text="Нет", callback_data=data_no),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
