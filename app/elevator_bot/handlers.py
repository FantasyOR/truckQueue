from __future__ import annotations

from datetime import date, timedelta
import asyncio

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db import SessionLocal
from app.elevator_bot.keyboards import (
    booking_actions_keyboard,
    elevators_keyboard,
    main_menu_keyboard,
)
from app.elevator_bot.states import ElevatorState
from app.models import Booking, BookingStatus, Elevator
from app.queue_logic import recalc_queue
from app.utils.time_utils import now_tz
from app.truck_bot import keyboards as driver_keyboards
from aiogram import Bot
from app.config import settings


router = Router()


def _format_booking(booking: Booking) -> str:
    tz_now = now_tz()
    slot_local = booking.slot_start.astimezone(tz_now.tzinfo)
    status_map = {
        BookingStatus.PENDING: "Запрос",
        BookingStatus.CONFIRMED: "Записан",
        BookingStatus.ARRIVED: "Прибыл",
        BookingStatus.UNLOADED: "Разгружен",
        BookingStatus.CANCELLED: "Отменён",
    }
    status = status_map.get(booking.status, booking.status)
    return (
        f"#{booking.id} | {slot_local.strftime('%Y-%m-%d %H:%M')}\n"
        f"Элеватор: {booking.elevator.name}\n"
        f"Номер: {booking.license_plate}\n"
        f"Водитель: @{booking.driver.telegram_username or booking.driver.telegram_user_id}\n"
        f"Статус: {status}"
    )


async def _select_elevator_prompt(message: Message, state: FSMContext) -> None:
    with SessionLocal() as session:
        elevators = [e.name for e in session.query(Elevator).order_by(Elevator.name).all()]
    if not elevators:
        await message.answer("Нет настроенных элеваторов. Добавьте в базе.")
        return
    await state.set_state(ElevatorState.choosing_elevator)
    await message.answer("Выберите элеватор для работы:", reply_markup=elevators_keyboard(elevators))


async def _get_selected_elevator_id(state: FSMContext) -> int | None:
    data = await state.get_data()
    return data.get("elevator_id")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _select_elevator_prompt(message, state)


@router.message(Command("change_elevator"))
async def cmd_change_elevator(message: Message, state: FSMContext) -> None:
    await _select_elevator_prompt(message, state)


@router.callback_query(F.data.startswith("elevator:"))
async def choose_elevator(call: CallbackQuery, state: FSMContext) -> None:
    name = call.data.split(":", 1)[1]
    with SessionLocal() as session:
        elevator = session.query(Elevator).filter_by(name=name).one_or_none()
    if elevator is None:
        await call.answer("Элеватор не найден", show_alert=True)
        return
    await state.update_data(elevator_id=elevator.id)
    await state.set_state(None)
    await call.message.edit_text(f"Элеватор выбран: {name}\nИспользуйте кнопки ниже.")
    await call.message.answer("Выберите действие:", reply_markup=main_menu_keyboard())
    await call.answer()


@router.message(Command("today"))
async def cmd_today(message: Message, state: FSMContext) -> None:
    elevator_id = await _get_selected_elevator_id(state)
    if not elevator_id:
        await _select_elevator_prompt(message, state)
        return
    today = date.today()
    with SessionLocal() as session:
        bookings = (
            session.query(Booking)
            .join(Elevator)
            .filter(
                Booking.date == today,
                Booking.status != BookingStatus.CANCELLED,
                Booking.elevator_id == elevator_id,
            )
            .order_by(Booking.slot_start)
            .all()
        )
        if not bookings:
            await message.answer("На сегодня бронирований нет.")
            return
        for booking in bookings:
            markup = booking_actions_keyboard(booking)
            await message.answer(
                _format_booking(booking), reply_markup=markup
            )


@router.message(Command("schedule"))
async def cmd_schedule(message: Message, state: FSMContext) -> None:
    elevator_id = await _get_selected_elevator_id(state)
    if not elevator_id:
        await _select_elevator_prompt(message, state)
        return
    target_day = date.today() + timedelta(days=1)
    with SessionLocal() as session:
        bookings = (
            session.query(Booking)
            .join(Elevator)
            .filter(
                Booking.date == target_day,
                Booking.status != BookingStatus.CANCELLED,
                Booking.elevator_id == elevator_id,
            )
            .order_by(Booking.slot_start)
            .all()
        )
        if not bookings:
            await message.answer("На завтра бронирований нет.")
            return
        for booking in bookings:
            await message.answer(_format_booking(booking))


@router.message(F.text.casefold() == "сегодня")
async def menu_today(message: Message, state: FSMContext) -> None:
    await cmd_today(message, state)


@router.message(F.text.casefold() == "завтра")
async def menu_schedule(message: Message, state: FSMContext) -> None:
    await cmd_schedule(message, state)


@router.message(F.text.casefold() == "сменить элеватор")
async def menu_change_elevator(message: Message, state: FSMContext) -> None:
    await cmd_change_elevator(message, state)


@router.callback_query(F.data.startswith("arrive:"))
async def mark_arrived(call: CallbackQuery, state: FSMContext) -> None:
    booking_id = int(call.data.split(":")[1])
    data = await state.get_data()
    elevator_id = data.get("elevator_id")
    with SessionLocal() as session:
        booking = session.get(Booking, booking_id)
        if booking is None:
            await call.answer("Бронирование не найдено", show_alert=True)
            return
        if elevator_id and booking.elevator_id != elevator_id:
            await call.answer("Недоступно для этого бота", show_alert=True)
            return
        booking.arrived_at = now_tz()
        booking.status = BookingStatus.ARRIVED
        recalc_queue(session, booking.elevator_id, booking.date)
        session.commit()
        markup = booking_actions_keyboard(booking)
        await call.message.edit_text(_format_booking(booking), reply_markup=markup)
        await call.answer("Прибытие отмечено")


@router.callback_query(F.data.startswith("unload:"))
async def mark_unloaded(call: CallbackQuery, state: FSMContext) -> None:
    booking_id = int(call.data.split(":")[1])
    data = await state.get_data()
    elevator_id = data.get("elevator_id")
    with SessionLocal() as session:
        booking = session.get(Booking, booking_id)
        if booking is None:
            await call.answer("Бронирование не найдено", show_alert=True)
            return
        if elevator_id and booking.elevator_id != elevator_id:
            await call.answer("Недоступно для этого бота", show_alert=True)
            return
        booking.unloaded_at = now_tz()
        booking.status = BookingStatus.UNLOADED
        session.commit()
        markup = booking_actions_keyboard(booking)
        await call.message.edit_text(_format_booking(booking), reply_markup=markup)
        await call.answer("Выгрузка отмечена")
        await _offer_next_now(session, booking)


@router.callback_query(F.data.startswith("cancel:"))
async def mark_cancelled(call: CallbackQuery, state: FSMContext) -> None:
    booking_id = int(call.data.split(":")[1])
    data = await state.get_data()
    elevator_id = data.get("elevator_id")
    with SessionLocal() as session:
        booking = session.get(Booking, booking_id)
        if booking is None:
            await call.answer("Бронирование не найдено", show_alert=True)
            return
        if elevator_id and booking.elevator_id != elevator_id:
            await call.answer("Недоступно для этого бота", show_alert=True)
            return
        booking.cancelled_at = now_tz()
        booking.status = BookingStatus.CANCELLED
        recalc_queue(session, booking.elevator_id, booking.date)
        session.commit()
        markup = booking_actions_keyboard(booking)
        if markup:
            await call.message.edit_text(_format_booking(booking), reply_markup=markup)
        else:
            await call.message.edit_text(_format_booking(booking))
        await call.answer("Бронирование отменено")


def _offer_next_now(session, unloaded_booking: Booking) -> None:
    """
    Notify next in queue (and optionally second if first declines).
    """
    if not unloaded_booking:
        return
    today = unloaded_booking.date
    recalc_queue(session, unloaded_booking.elevator_id, today)
    session.flush()
    # получаем список очереди без отмененных/разгруженных
    candidates = (
        session.query(Booking)
        .filter(
            Booking.elevator_id == unloaded_booking.elevator_id,
            Booking.date == today,
            Booking.status.notin_([BookingStatus.CANCELLED, BookingStatus.UNLOADED]),
        )
        .order_by(Booking.queue_index)
        .all()
    )
    if not candidates:
        return
    first = candidates[0]
    fallback = candidates[1].id if len(candidates) > 1 else None

    driver = first.driver
    if driver is None:
        return
    bot = Bot(token=settings.truck_bot_token)
    text = (
        "Слот освободился. Можете подъехать сейчас?\n"
        f"Элеватор: {first.elevator.name}\n"
        f"Бронь: {first.date} {first.slot_start.strftime('%H:%M')}"
    )
    markup = driver_keyboards.inline_offer_keyboard(first.id, fallback)
    # fire and forget
    asyncio.get_event_loop().create_task(
        bot.send_message(driver.telegram_user_id, text, reply_markup=markup)
    )
