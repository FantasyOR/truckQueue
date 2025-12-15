from __future__ import annotations

from datetime import date, timedelta

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.config import settings
from app.db import SessionLocal
from app.models import Booking, BookingStatus, Driver, Elevator
from app.queue_logic import recalc_queue
from app.truck_bot import keyboards
from app.truck_bot.states import BookingState
from app.utils.time_utils import build_daily_slots, combine_date_time, now_tz, parse_date
from aiogram.types import CallbackQuery


router = Router()


STATUS_TEXT = {
    BookingStatus.PENDING: "Запрос",
    BookingStatus.CONFIRMED: "Записан",
    BookingStatus.ARRIVED: "Прибыл",
    BookingStatus.UNLOADED: "Разгружен",
    BookingStatus.CANCELLED: "Отменён",
}


def _get_or_create_driver(session, tg_user_id: int, tg_username: str | None) -> Driver:
    driver = session.query(Driver).filter_by(telegram_user_id=tg_user_id).one_or_none()
    if driver is None:
        driver = Driver(telegram_user_id=tg_user_id, telegram_username=tg_username)
        session.add(driver)
        session.flush()
    return driver


def _available_slots(session, elevator: Elevator, booking_date: date) -> list[str]:
    existing = (
        session.query(Booking)
        .filter(
            Booking.elevator_id == elevator.id,
            Booking.date == booking_date,
            Booking.status != BookingStatus.CANCELLED,
        )
        .all()
    )
    taken = {b.slot_start.timetz() for b in existing}
    slots = build_daily_slots(elevator.work_day_start, elevator.work_day_end, elevator.bookable_slots_per_day)
    now = now_tz()
    available = []
    for slot_start, _ in slots:
        if slot_start not in taken:
            if booking_date == now.date():
                # не предлагать слоты, которые уже начались
                if combine_date_time(booking_date, slot_start) <= now:
                    continue
            available.append(slot_start.strftime("%H:%M"))
    return available


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Привет! Я бот очереди на элеватор.\n"
        "Выберите действие кнопками ниже.",
        reply_markup=keyboards.main_menu_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Доступные действия:\n"
        "• Записаться — выбрать дату и слот.\n"
        "• Мои бронирования — показать активные записи.\n"
        "• Помощь — подсказка по шагам.",
        reply_markup=keyboards.main_menu_keyboard(),
    )


@router.message(Command("my_bookings"))
async def cmd_my_bookings(message: Message) -> None:
    with SessionLocal() as session:
        driver = session.query(Driver).filter_by(telegram_user_id=message.from_user.id).one_or_none()
        if driver is None:
            await message.answer("Бронирования не найдены.")
            return
        now = now_tz()
        bookings = (
            session.query(Booking)
            .filter(
                Booking.driver_id == driver.id,
                Booking.status != BookingStatus.CANCELLED,
                Booking.slot_end >= now - timedelta(days=1),
            )
            .order_by(Booking.slot_start)
            .all()
        )
        if not bookings:
            await message.answer("Бронирования не найдены.")
            return
        lines = []
        for b in bookings:
            status = STATUS_TEXT.get(b.status, b.status)
            lines.append(
                f"{b.date.isoformat()} {b.slot_start.astimezone(now.tzinfo).strftime('%H:%M')} — элеватор {b.elevator.name}, номер {b.license_plate}, статус {status}"
            )
        await message.answer("\n".join(lines))
    await message.answer("Выберите действие:", reply_markup=keyboards.main_menu_keyboard())


@router.message(Command("book"))
async def cmd_book(message: Message, state: FSMContext) -> None:
    with SessionLocal() as session:
        elevators = session.query(Elevator).order_by(Elevator.name).all()
        if not elevators:
            await message.answer(
                "Элеваторы не настроены. Свяжитесь с диспетчером.",
                reply_markup=keyboards.main_menu_keyboard(),
            )
            return
    await state.set_state(BookingState.choosing_elevator)
    await message.answer("Выберите элеватор:", reply_markup=keyboards.elevators_keyboard(elevators))
    # no main menu here to keep focus on flow


@router.message(F.text.casefold() == "записаться")
async def menu_book(message: Message, state: FSMContext) -> None:
    await cmd_book(message, state)


@router.message(F.text.casefold() == "мои бронирования")
async def menu_my_bookings(message: Message, state: FSMContext) -> None:
    await cmd_my_bookings(message)


@router.message(F.text.casefold() == "помощь")
async def menu_help(message: Message, state: FSMContext) -> None:
    await cmd_help(message)


@router.callback_query(F.data.startswith("come:"))
async def on_come_offer(callback: CallbackQuery) -> None:
    """
    Handle dispatcher offer to come now.
    callback data: come:<action>:<booking_id>[:<fallback_id>]
    """
    parts = callback.data.split(":")
    _, action, booking_id, *rest = parts
    booking_id = int(booking_id)
    fallback_id = int(rest[0]) if rest else None

    with SessionLocal() as session:
        booking = session.get(Booking, booking_id)
        if booking is None:
            await callback.answer("Бронь не найдена", show_alert=True)
            return
        if booking.driver.telegram_user_id != callback.from_user.id:
            await callback.answer("Это предложение не для вас", show_alert=True)
            return

        if action == "yes":
            now = now_tz()
            booking.slot_start = now
            booking.slot_end = now + timedelta(minutes=settings.slot_duration_minutes)
            booking.updated_at = now
            recalc_queue(session, booking.elevator_id, booking.date)
            session.commit()
            await callback.message.edit_text(
                f"Спасибо! Подъезжайте сейчас.\n"
                f"Элеватор: {booking.elevator.name}\n"
                f"Слот: сейчас–{booking.slot_end.astimezone(now.tzinfo).strftime('%H:%M')}\n"
                f"Номер: {booking.license_plate}"
            )
            await callback.answer("Принято")
        elif action == "no":
            session.commit()
            await callback.message.edit_text("Вы отказались. Предложим следующему.")
            await callback.answer("Отказ")
            if fallback_id:
                _notify_next_offer(session, fallback_id)
        else:
            await callback.answer()


def _notify_next_offer(session, booking_id: int) -> None:
    from aiogram import Bot

    booking = session.get(Booking, booking_id)
    if booking is None:
        return
    driver = booking.driver
    if driver is None:
        return
    bot = Bot(settings.truck_bot_token)
    text = (
        f"Слот освободился. Можете подъехать сейчас?\n"
        f"Элеватор: {booking.elevator.name}\n"
        f"Бронь: {booking.date} {booking.slot_start.strftime('%H:%M')}\n"
        "Принять предложение?"
    )
    fallback = ""
    # no further offers beyond this one per требования
    markup = keyboards.inline_offer_keyboard(booking.id, fallback_id=None)
    asyncio.get_event_loop().create_task(
        bot.send_message(driver.telegram_user_id, text, reply_markup=markup)
    )


@router.message(BookingState.choosing_elevator)
async def choose_elevator(message: Message, state: FSMContext) -> None:
    with SessionLocal() as session:
        elevator = session.query(Elevator).filter_by(name=message.text).one_or_none()
        if elevator is None:
            await message.answer("Не могу найти такой элеватор. Выберите из списка.")
            return
    await state.update_data(elevator_id=elevator.id)
    await state.set_state(BookingState.choosing_date)
    await message.answer("Выберите дату (формат YYYY-MM-DD):", reply_markup=keyboards.dates_keyboard())


@router.message(BookingState.choosing_date)
async def choose_date(message: Message, state: FSMContext) -> None:
    try:
        booking_date = parse_date(message.text.strip())
    except ValueError:
        await message.answer("Дата должна быть в формате YYYY-MM-DD.")
        return
    if booking_date < date.today():
        await message.answer("Нельзя выбрать прошедшую дату.")
        return

    data = await state.get_data()
    elevator_id = data.get("elevator_id")
    with SessionLocal() as session:
        elevator = session.query(Elevator).get(elevator_id)
        if elevator is None:
            await message.answer("Элеватор не найден, начните заново /book.")
            await state.clear()
            return
        slots = _available_slots(session, elevator, booking_date)
    if not slots:
        await message.answer("На эту дату нет свободных слотов. Выберите другую дату.", reply_markup=keyboards.dates_keyboard())
        return
    await state.update_data(date=booking_date.isoformat(), slots=slots)
    await state.set_state(BookingState.choosing_slot)
    await message.answer("Выберите время слота:", reply_markup=keyboards.slots_keyboard(slots))


@router.message(BookingState.choosing_slot)
async def choose_slot(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    slots: list[str] = data.get("slots", [])
    if message.text not in slots:
        await message.answer("Выберите время из списка.")
        return
    await state.update_data(slot_time=message.text)
    await state.set_state(BookingState.entering_license_plate)
    await message.answer("Введите номер грузовика (госномер):", reply_markup=keyboards.remove_keyboard())


@router.message(BookingState.entering_license_plate)
async def enter_license(message: Message, state: FSMContext) -> None:
    plate = message.text.strip()
    if not plate:
        await message.answer("Номер не может быть пустым.")
        return
    await state.update_data(license_plate=plate)
    data = await state.get_data()
    text = (
        "Подтвердите бронирование:\n"
        f"Элеватор: {data.get('elevator_id')}\n"
        f"Дата: {data.get('date')}\n"
        f"Время: {data.get('slot_time')}\n"
        f"Номер: {plate}"
    )
    await state.set_state(BookingState.confirming)
    await message.answer(text, reply_markup=keyboards.confirmation_keyboard())


@router.message(BookingState.confirming)
async def confirm_booking(message: Message, state: FSMContext) -> None:
    if message.text not in {"Подтвердить", "Отмена"}:
        await message.answer("Выберите действие: Подтвердить или Отмена.")
        return
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Бронирование отменено.", reply_markup=keyboards.remove_keyboard())
        await message.answer("Что дальше?", reply_markup=keyboards.main_menu_keyboard())
        return

    data = await state.get_data()
    with SessionLocal() as session:
        elevator = session.query(Elevator).get(data["elevator_id"])
        if elevator is None:
            await message.answer("Элеватор не найден. Начните заново /book.")
            await state.clear()
            await message.answer("Выберите действие:", reply_markup=keyboards.main_menu_keyboard())
            return
        booking_date = parse_date(data["date"])
        available_slots = _available_slots(session, elevator, booking_date)
        if data["slot_time"] not in available_slots:
            await message.answer("Слот уже занят, выберите другой /book.")
            await state.clear()
            await message.answer("Выберите действие:", reply_markup=keyboards.main_menu_keyboard())
            return

        driver = _get_or_create_driver(session, message.from_user.id, message.from_user.username)
        slot_hour, slot_minute = map(int, data["slot_time"].split(":"))
        slot_time = elevator.work_day_start.replace(hour=slot_hour, minute=slot_minute, second=0, microsecond=0)
        slot_start_dt = combine_date_time(booking_date, slot_time)
        slot_end_dt = slot_start_dt + timedelta(minutes=settings.slot_duration_minutes)
        booking = Booking(
            driver_id=driver.id,
            elevator_id=elevator.id,
            license_plate=data["license_plate"],
            date=booking_date,
            slot_start=slot_start_dt,
            slot_end=slot_end_dt,
            status=BookingStatus.CONFIRMED,
        )
        session.add(booking)
        session.flush()
        recalc_queue(session, elevator.id, booking_date)
        session.commit()
        await state.clear()
        await message.answer(
            "Бронирование подтверждено.\n"
            f"Элеватор: {elevator.name}\n"
            f"Дата: {booking_date}\n"
            f"Время: {data['slot_time']}\n"
            f"Номер: {booking.license_plate}",
            reply_markup=keyboards.main_menu_keyboard(),
        )
