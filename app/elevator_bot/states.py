from aiogram.fsm.state import State, StatesGroup


class ElevatorState(StatesGroup):
    choosing_elevator = State()
