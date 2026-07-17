import asyncio

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


CHANNEL_ID = "@vexa_group"
PROXY = "http://127.0.0.1:10809"


text = """&#128640; <b>Большое обновление поиска в Vexa</b>

Мы полностью пересмотрели обработку ключевых слов, синонимов и входящих сообщений.

Раньше объявления работодателей могли попадать в совпадения из-за слишком широкого поиска. Например, Vexa могла ошибочно считать слова «ищу», «нужен», «ищем» и «требуется» похожими.

Теперь эта логика переделана.

<pre>Что изменилось       Результат
────────────────────────────────
Синонимы             Стали точнее
Ключевые фразы       Учитывается порядок слов
Границы слов         Убраны ложные совпадения
Работодатели         Отсеиваются автоматически
Боты и реклама       Не попадают в результаты
Хештеги и ссылки     Не запускают совпадение
Тихие часы           Очередь проверяется повторно</pre>

<b>Vexa теперь распознаёт признаки вакансий:</b>

• «требуется» и «требуются»
• «нужен сотрудник» и «ищем людей»
• обязанности, условия и график
• ставка, тариф и оплата за смену
• массовый набор сотрудников
• шаблонные публикации работодателей
• рекламные сообщения и объявления ботов

При этом сообщения кандидатов продолжают находиться:

<pre>ищу работу грузчиком
ищу подработку на складе
мне нужна работа водителем
готов выйти завтра
есть опыт комплектовщиком</pre>

<blockquote>Теперь Vexa старается отличать человека, который ищет работу, от работодателя, который ищет сотрудника.</blockquote>

Также исправили системные уведомления: жирный текст, курсив и цитаты теперь отображаются правильно, без технических тегов.

Продолжаем улучшать качество совпадений на основе реальных сообщений из Telegram."""


keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚀 Открыть Vexa",
                url="https://t.me/vexahelp_bot",
            )
        ],
        [
            InlineKeyboardButton(
                text="📗 База ключей",
                url=(
                    "https://docs.google.com/spreadsheets/d/"
                    "1j2vgRFPEO40gJKQoFX9hV6Md41RIxEANjwSe2cpbPa0/"
                    "edit?gid=1403825979#gid=1403825979"
                ),
            )
        ],
        [
            InlineKeyboardButton(
                text="💬 Поддержка",
                url="https://t.me/olenchuk_b",
            )
        ],
    ]
)


async def main() -> None:
    bot_token = input("Вставьте токен Telegram-бота: ").strip()

    if not bot_token:
        raise RuntimeError("Токен бота не указан.")

    session = AiohttpSession(proxy=PROXY)
    bot = Bot(token=bot_token, session=session)

    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        print("Пост успешно отправлен.")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())