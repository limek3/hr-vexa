from aiogram.fsm.state import State, StatesGroup


class CreateSearch(StatesGroup):
    title = State()
    keywords = State()
    minus_words = State()
    sources = State()
