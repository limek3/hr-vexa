import asyncio
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8906047898:AAE_XV7f9ufKvQB_e8d_EbaTFkKIawnHepk"
CHANNEL_ID = "@vexa_group"

PROXY = "http://127.0.0.1:10809"

text = """
Небольшое обновление Vexa сегодня.

Чуть доработали подключение источников и сделали поведение бота понятнее.

Что изменилось:

<blockquote>• Vexa теперь пробует сама подключаться к публичным группам и каналам, если там есть кнопка «Присоединиться»
• для закрытых источников можно указывать invite-ссылку вида https://t.me/+...
• добавили очередь подключения, чтобы аккаунт не пытался заходить во все источники сразу
• появились понятные статусы источников: в очереди, вступаем, доступен, нет доступа, заявка отправлена
• если источник не удалось подключить, бот напишет причину
• добавили кнопку «Проверить источники заново»
• обновили подсказки в боте, чтобы было понятнее, какие ссылки можно указывать </blockquote>

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