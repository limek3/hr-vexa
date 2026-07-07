from aiogram import Dispatcher

from app.bot.handlers import actions, admin, create_search, menu, searches, start
from app.bot.middleware import DbSessionMiddleware


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.update.middleware(DbSessionMiddleware())
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(create_search.router)
    dp.include_router(searches.router)
    dp.include_router(actions.router)
    dp.include_router(menu.router)
    return dp
