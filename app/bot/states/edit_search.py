from aiogram.fsm.state import State, StatesGroup


class EditSearch(StatesGroup):
    title = State()
    keywords = State()
    minus_words = State()
    sources = State()
