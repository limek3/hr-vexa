from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import heading, metric, step_line, text_value
from app.bot.keyboards.labels import CANCEL, LEGACY_NEW_SEARCH, NEW_SEARCH, SKIP
from app.bot.keyboards.menu import cancel_menu, main_menu, skip_menu
from app.bot.messages import KEYWORD_BASE_HINT
from app.bot.states.create_search import CreateSearch
from app.db.repositories.searches import create_search
from app.db.repositories.users import get_or_create_user
from app.services.limits import max_sources_per_search, sources_limit_error
from app.services.policy import find_forbidden_terms, forbidden_terms_message
from app.utils.links import split_sources
from app.utils.text import split_terms

router = Router()


@router.message(StateFilter(CreateSearch), F.text == CANCEL)
async def cancel_create_search(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        f"{heading('Создание поиска отменено')}\n"
        "\n"
        "Вы можете начать заново в любой момент.",
        reply_markup=main_menu(),
    )


@router.message(lambda message: message.text in {NEW_SEARCH, LEGACY_NEW_SEARCH})
async def create_search_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(CreateSearch.title)
    await message.answer(
        f"{heading('Новый поиск')}\n"
        "\n"
        f"{step_line(1, 4, 'название')}\n\n"
        "Напишите короткое название, чтобы потом легко найти поиск в списке.\n\n"
        "<b>Примеры</b>\n"
        "<blockquote>Аренда Москва\nЗаявки на ремонт\nОтзывы о бренде\nТендеры поставки</blockquote>",
        reply_markup=cancel_menu(),
    )


@router.message(CreateSearch.title)
async def set_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if len(title) < 2:
        await message.answer(
            "Слишком короткое название. Напишите, например: <code>Аренда Москва</code>",
            reply_markup=cancel_menu(),
        )
        return

    await state.update_data(title=title)
    await state.set_state(CreateSearch.keywords)
    await message.answer(
        f"{heading('Новый поиск')}\n"
        "\n"
        f"{step_line(2, 4, 'ключевые слова')}\n\n"
        "Пишите слова или фразы, которые должны быть в нужном сообщении.\n"
        "Лучше каждую фразу с новой строки.\n\n"
        f"{KEYWORD_BASE_HINT}\n\n"
        "<b>Примеры</b>\n"
        "<blockquote>сдам квартиру\nнужен ремонт\nищу поставщика\nотзыв vexa\nкурьер</blockquote>",
        reply_markup=cancel_menu(),
        disable_web_page_preview=True,
    )


@router.message(CreateSearch.keywords)
async def set_keywords(message: Message, state: FSMContext) -> None:
    keywords = split_terms(message.text or "")
    if not keywords:
        await message.answer("Нужно хотя бы одно ключевое слово.", reply_markup=cancel_menu())
        return
    forbidden = find_forbidden_terms(keywords)
    if forbidden:
        await message.answer(forbidden_terms_message(forbidden), reply_markup=cancel_menu())
        return

    await state.update_data(keywords=keywords)
    await state.set_state(CreateSearch.minus_words)
    await message.answer(
        f"{heading('Новый поиск')}\n"
        "\n"
        f"{step_line(3, 4, 'минус-слова')}\n\n"
        "Если в сообщении есть минус-слово, уведомление не придет.\n\n"
        f"{KEYWORD_BASE_HINT}\n\n"
        "<b>Примеры</b>\n"
        "<blockquote>реклама\nфраншиза\nобучение\nнеактуально</blockquote>\n\n"
        "Если минус-слова не нужны, нажмите <b>Пропустить</b>.",
        reply_markup=skip_menu(),
        disable_web_page_preview=True,
    )


@router.message(CreateSearch.minus_words)
async def set_minus_words(message: Message, state: FSMContext) -> None:
    minus_words = [] if message.text == SKIP else split_terms(message.text or "")
    source_limit = max_sources_per_search()
    await state.update_data(minus_words=minus_words)
    await state.set_state(CreateSearch.sources)
    await message.answer(
        f"{heading('Новый поиск')}\n"
        "\n"
        f"{step_line(4, 4, 'источники')}\n\n"
        "Отправьте каналы, группы или группы комментариев, каждый источник с новой строки.\n"
        f"Сейчас можно добавить до <b>{source_limit}</b> источников на один поиск.\n\n"
        "<b>Примеры</b>\n"
        "<blockquote>@vexa_group\nhttps://t.me/vexa_group\nhttps://t.me/+invite</blockquote>\n\n"
        "Публичные источники можно отправлять как <code>@username</code> или ссылку. "
        "Если там есть кнопка «Присоединиться», Vexa попробует вступить сама.\n\n"
        "Для закрытых источников нужна invite-ссылка <code>https://t.me/+...</code> "
        "или добавление аккаунта Vexa админом. Если вход через заявку, мониторинг начнется "
        "после одобрения.",
        reply_markup=cancel_menu(),
        disable_web_page_preview=True,
    )


@router.message(CreateSearch.sources)
async def set_sources(message: Message, state: FSMContext, session: AsyncSession) -> None:
    sources = split_sources(message.text or "")
    if not sources:
        await message.answer(
            "Не вижу источников. Отправьте <code>@username</code>, ссылку <code>https://t.me/...</code> "
            "или invite-ссылку <code>https://t.me/+...</code>, каждую с новой строки.",
            reply_markup=cancel_menu(),
        )
        return

    limit_error = sources_limit_error(len(sources))
    if limit_error:
        await message.answer(limit_error, reply_markup=cancel_menu())
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
        f"{heading('Поиск создан')}\n"
        "\n"
        f"{text_value('Название', search.title)}\n"
        f"{metric('Ключевых слов', len(data['keywords']))}\n"
        f"{metric('Минус-слов', len(data['minus_words']))}\n"
        f"{metric('Источников', len(sources))}\n\n"
        "<b>⚠️ Важно</b>\n"
        "<blockquote>Статус источников сначала будет «проверяется». "
        "Когда Vexa получит доступ, поиск начнет приносить совпадения.</blockquote>",
        reply_markup=main_menu(),
        disable_web_page_preview=True,
    )
