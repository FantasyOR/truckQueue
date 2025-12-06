from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def booking_actions_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Отметить прибытие", callback_data=f"arrive:{booking_id}"),
                InlineKeyboardButton(text="Отметить выгрузку", callback_data=f"unload:{booking_id}"),
            ],
            [
                InlineKeyboardButton(text="Отменить", callback_data=f"cancel:{booking_id}"),
            ],
        ]
    )
