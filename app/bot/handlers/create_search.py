from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import html
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
        "<b>Новый поиск</b>\n"
        "Шаг 1 из 4: название\n\n"
        "Напишите короткое название, чтобы потом легко найти поиск в списке.\n\n"
        "<blockquote>Вахта Москва\nКурьеры СПб\nКомплектовщики Казань</blockquote>",
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
        "<b>Шаг 2 из 4: ключевые слова</b>\n\n"
        "Пишите слова или фразы, которые должны быть в сообщении кандидата.\n"
        "Лучше каждую фразу с новой строки.\n\n"
        "<blockquote>вахта\nкомплектовщик\nразнорабочий</blockquote>",
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
        "<b>Шаг 3 из 4: минус-слова</b>\n\n"
        "Если в сообщении есть минус-слово, уведомление не придет.\n\n"
        "<blockquote>обучение\nфраншиза\nинвестиции</blockquote>\n\n"
        "Если минус-слова не нужны, нажмите <b>Пропустить</b>.",
        reply_markup=skip_menu(),
    )


@router.message(CreateSearch.minus_words)
async def set_minus_words(message: Message, state: FSMContext) -> None:
    minus_words = [] if message.text == SKIP else split_terms(message.text or "")
    await state.update_data(minus_words=minus_words)
    await state.set_state(CreateSearch.sources)
    await message.answer(
        "<b>Шаг 4 из 4: источники</b>\n\n"
        "Отправьте каналы или группы, каждый источник с новой строки.\n\n"
        "<blockquote>@channel\nhttps://t.me/channel\nhttps://t.me/+invite</blockquote>\n\n"
        "HR Vexa проверит доступ и начнет слушать новые сообщения.",
        reply_markup=cancel_menu(),
        disable_web_page_preview=True,
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
        f"<b>Название:</b> {html(search.title)}\n"
        f"<b>Ключевых слов:</b> {len(data['keywords'])}\n"
        f"<b>Минус-слов:</b> {len(data['minus_words'])}\n"
        f"<b>Источников:</b> {len(sources)}\n\n"
        "<blockquote>Статус источников сначала будет «проверяется». "
        "Когда monitor получит доступ, поиск начнет приносить совпадения.</blockquote>",
        reply_markup=main_menu(),
        disable_web_page_preview=True,
    )
