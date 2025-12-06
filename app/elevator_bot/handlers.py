from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.db import SessionLocal
from app.elevator_bot.keyboards import booking_actions_keyboard
from app.models import Booking, BookingStatus, Elevator
from app.queue_logic import recalc_queue
from app.utils.csv_export import bookings_to_csv
from app.utils.time_utils import now_tz


router = Router()


def _format_booking(booking: Booking) -> str:
    tz_now = now_tz()
    slot_local = booking.slot_start.astimezone(tz_now.tzinfo)
    status = booking.status
    return (
        f"#{booking.id} | {slot_local.strftime('%Y-%m-%d %H:%M')} | позиция {booking.queue_index}\n"
        f"Элеватор: {booking.elevator.name}\n"
        f"Номер: {booking.license_plate}\n"
        f"Водитель: @{booking.driver.telegram_username or booking.driver.telegram_user_id}\n"
        f"Статус: {status}"
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Бот диспетчера. Команды: /today — сегодняшние бронирования, /schedule — расписание на 3 дня, /export — CSV за сегодня."
    )


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    today = date.today()
    with SessionLocal() as session:
        bookings = (
            session.query(Booking)
            .join(Elevator)
            .filter(Booking.date == today, Booking.status != BookingStatus.CANCELLED)
            .order_by(Booking.slot_start)
            .all()
        )
        if not bookings:
            await message.answer("На сегодня бронирований нет.")
            return
        for booking in bookings:
            await message.answer(_format_booking(booking), reply_markup=booking_actions_keyboard(booking.id))


@router.message(Command("schedule"))
async def cmd_schedule(message: Message) -> None:
    start_day = date.today()
    end_day = start_day + timedelta(days=3)
    with SessionLocal() as session:
        bookings = (
            session.query(Booking)
            .join(Elevator)
            .filter(
                Booking.date >= start_day,
                Booking.date <= end_day,
                Booking.status != BookingStatus.CANCELLED,
            )
            .order_by(Booking.slot_start)
            .all()
        )
        if not bookings:
            await message.answer("Нет бронирований в ближайшие дни.")
            return
        lines = []
        for booking in bookings:
            lines.append(_format_booking(booking))
        await message.answer("\n\n".join(lines))


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    today = date.today()
    with SessionLocal() as session:
        bookings = (
            session.query(Booking)
            .filter(Booking.date == today)
            .order_by(Booking.slot_start)
            .all()
        )
        data = bookings_to_csv(bookings)
    buffer = BytesIO(data)
    buffer.seek(0)
    await message.answer_document(FSInputFile(buffer, filename=f"schedule_{today}.csv"))


@router.callback_query(F.data.startswith("arrive:"))
async def mark_arrived(call: CallbackQuery) -> None:
    booking_id = int(call.data.split(":")[1])
    with SessionLocal() as session:
        booking = session.get(Booking, booking_id)
        if booking is None:
            await call.answer("Бронирование не найдено", show_alert=True)
            return
        booking.arrived_at = now_tz()
        booking.status = BookingStatus.ARRIVED
        recalc_queue(session, booking.elevator_id, booking.date)
        session.commit()
        await call.message.edit_text(_format_booking(booking), reply_markup=booking_actions_keyboard(booking.id))
        await call.answer("Прибытие отмечено")


@router.callback_query(F.data.startswith("unload:"))
async def mark_unloaded(call: CallbackQuery) -> None:
    booking_id = int(call.data.split(":")[1])
    with SessionLocal() as session:
        booking = session.get(Booking, booking_id)
        if booking is None:
            await call.answer("Бронирование не найдено", show_alert=True)
            return
        booking.unloaded_at = now_tz()
        booking.status = BookingStatus.UNLOADED
        session.commit()
        await call.message.edit_text(_format_booking(booking), reply_markup=booking_actions_keyboard(booking.id))
        await call.answer("Выгрузка отмечена")


@router.callback_query(F.data.startswith("cancel:"))
async def mark_cancelled(call: CallbackQuery) -> None:
    booking_id = int(call.data.split(":")[1])
    with SessionLocal() as session:
        booking = session.get(Booking, booking_id)
        if booking is None:
            await call.answer("Бронирование не найдено", show_alert=True)
            return
        booking.cancelled_at = now_tz()
        booking.status = BookingStatus.CANCELLED
        recalc_queue(session, booking.elevator_id, booking.date)
        session.commit()
        await call.message.edit_text(_format_booking(booking))
        await call.answer("Бронирование отменено")
