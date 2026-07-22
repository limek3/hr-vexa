from aiogram.fsm.state import State, StatesGroup


class AdminBroadcast(StatesGroup):
    message = State()
    button = State()
    preview = State()
