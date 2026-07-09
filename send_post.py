import asyncio
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8906047898:AAE_XV7f9ufKvQB_e8d_EbaTFkKIawnHepk"
CHANNEL_ID = "@vexa_group"

PROXY = "http://127.0.0.1:10809"

text = """

&#128218; <b>Учимся правильно настраивать поиски в Vexa.</b>

Главная ошибка — писать слишком общие ключи: «работа», «склад», «грузчик». Так бот будет ловить всё подряд, включая вакансии от работодателей.

Лучше писать так, как написал бы сам кандидат: «ищу работу», «готов выйти», «есть опыт».

<b>Пример: разнорабочий / склад / производство</b>

Ключи:
<pre>ищу работу разнорабочим
ищу подработку разнорабочим
готов выйти на смену
ищу работу на складе
ищу подработку на складе
грузчик ищет работу
комплектовщик ищет работу
работал на складе
есть опыт на складе
ищу вахту
готов на вахту</pre>

Минус-слова:
<pre>требуется
требуются
вакансия
приглашаем
мы предлагаем
условия
обязанности
зарплата от
ставка
смена
общежитие
питание
оформление
акция</pre>

Коротко: ключи помогают найти кандидата, минус-слова убирают вакансии и рекламу.

<blockquote>Специально для вас собрали готовую базу под вакансии с ключами и минус-словами. Можно открыть, выбрать профессию и сразу скопировать готовый блок для Vexa.</blockquote>

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
            text="📗 База ключей",
            url="https://docs.google.com/spreadsheets/d/1j2vgRFPEO40gJKQoFX9hV6Md41RIxEANjwSe2cpbPa0/edit?gid=1403825979#gid=1403825979"
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