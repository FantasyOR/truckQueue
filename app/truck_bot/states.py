from aiogram.fsm.state import State, StatesGroup


class BookingState(StatesGroup):
    choosing_elevator = State()
    choosing_date = State()
    choosing_slot = State()
    entering_license_plate = State()
    confirming = State()
