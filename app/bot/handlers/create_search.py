from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.labels import CANCEL, LEGACY_NEW_SEARCH, NEW_SEARCH, SKIP
from app.bot.keyboards.menu import cancel_menu, main_menu, skip_menu
from app.bot.states.create_search import CreateSearch
from app.db.repositories.searches import create_search
from app.db.repositories.users import get_or_create_user
from app.utils.links import split_sources
from app.utils.text import split_terms

router = Router()


@router.message(StateFilter(CreateSearch), F.text == CANCEL)
async def cancel_create_search(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "<b>Создание поиска отменено.</b>\n\n"
        "Вы можете начать заново в любой момент.",
        reply_markup=main_menu(),
    )


@router.message(lambda message: message.text in {NEW_SEARCH, LEGACY_NEW_SEARCH})
async def create_search_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(CreateSearch.title)
    await message.answer(
        "<b>Новый поиск</b>\n\n"
        "Шаг 1 из 4. Напишите короткое название.\n\n"
        "Примеры:\n"
        "<code>Вахта Москва</code>\n"
        "<code>Курьеры СПб</code>\n"
        "<code>Комплектовщики Казань</code>",
        reply_markup=cancel_menu(),
    )


@router.message(CreateSearch.title)
async def set_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if len(title) < 2:
        await message.answer(
            "Слишком короткое название. Напишите, например: <code>Курьеры СПб</code>",
            reply_markup=cancel_menu(),
        )
        return

    await state.update_data(title=title)
    await state.set_state(CreateSearch.keywords)
    await message.answer(
        "<b>Шаг 2 из 4. Ключевые слова</b>\n\n"
        "Отправьте слова или фразы, по которым нужно искать кандидатов.\n"
        "Можно через запятую или с новой строки.\n\n"
        "Пример:\n"
        "<code>вахта\nкомплектовщик\nразнорабочий</code>",
        reply_markup=cancel_menu(),
    )


@router.message(CreateSearch.keywords)
async def set_keywords(message: Message, state: FSMContext) -> None:
    keywords = split_terms(message.text or "")
    if not keywords:
        await message.answer("Нужно хотя бы одно ключевое слово.", reply_markup=cancel_menu())
        return

    await state.update_data(keywords=keywords)
    await state.set_state(CreateSearch.minus_words)
    await message.answer(
        "<b>Шаг 3 из 4. Минус-слова</b>\n\n"
        "Эти слова исключат неподходящие сообщения.\n\n"
        "Пример:\n"
        "<code>обучение\nфраншиза\nинвестиции</code>\n\n"
        "Если минус-слова не нужны, нажмите <b>Пропустить</b>.",
        reply_markup=skip_menu(),
    )


@router.message(CreateSearch.minus_words)
async def set_minus_words(message: Message, state: FSMContext) -> None:
    minus_words = [] if message.text == SKIP else split_terms(message.text or "")
    await state.update_data(minus_words=minus_words)
    await state.set_state(CreateSearch.sources)
    await message.answer(
        "<b>Шаг 4 из 4. Источники</b>\n\n"
        "Отправьте Telegram-источники, каждый с новой строки.\n\n"
        "Поддерживается:\n"
        "<code>@channel\nhttps://t.me/channel\nhttps://t.me/+invite</code>\n\n"
        "После сохранения worker проверит доступ и начнет слушать новые сообщения.",
        reply_markup=cancel_menu(),
    )


@router.message(CreateSearch.sources)
async def set_sources(message: Message, state: FSMContext, session: AsyncSession) -> None:
    sources = split_sources(message.text or "")
    if not sources:
        await message.answer(
            "Не вижу источников. Отправьте <code>@username</code> или ссылки <code>t.me</code>, "
            "каждую с новой строки.",
            reply_markup=cancel_menu(),
        )
        return

    if not message.from_user:
        return

    user = await get_or_create_user(session, message.from_user)
    data = await state.get_data()
    search = await create_search(
        session,
        user_id=user.id,
        title=data["title"],
        keywords=data["keywords"],
        minus_words=data["minus_words"],
        sources=sources,
    )
    await state.clear()

    await message.answer(
        "<b>Поиск создан</b>\n\n"
        f"<b>Название:</b> {search.title}\n"
        f"<b>Ключевых слов:</b> {len(data['keywords'])}\n"
        f"<b>Минус-слов:</b> {len(data['minus_words'])}\n"
        f"<b>Источников:</b> {len(sources)}\n\n"
        "Monitor-worker проверит доступ к источникам и начнет отслеживать новые сообщения.",
        reply_markup=main_menu(),
    )
