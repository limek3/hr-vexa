import asyncio
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8906047898:AAE_XV7f9ufKvQB_e8d_EbaTFkKIawnHepk"
CHANNEL_ID = "@vexa_group"

PROXY = "http://127.0.0.1:10809"

text = """
Небольшое обновление Vexa за ночь.

За ночь немного улучшили бота и сделали работу с ним удобнее.

Что изменилось:
<blockquote>• добавили статистику по поискам, источникам и найденным совпадениям
• почистили оформление совпадений, теперь уведомления читаются проще
• поправили визуальную составляющую сообщений и меню
• списки с поисками теперь отображаются кнопками, так удобнее открывать и управлять нужным поиском
• тихие часы теперь работают умнее: ночью бот не беспокоит, но найденные совпадения не теряются и приходят после 07:00</blockquote>

Можно пользоваться дальше и тестировать на своих Telegram-источниках.

"""

keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(
            text="🚀 Открыть бота",
            url="https://t.me/vexahelp_bot"
        )
    ],
    [
        InlineKeyboardButton(
            text="💬 Поддержка",
            url="https://t.me/olenchuk_b"
        )
    ]
])


async def main():
    session = AiohttpSession(proxy=PROXY)
    bot = Bot(token=BOT_TOKEN, session=session)

    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        print("Пост отправлен.")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())