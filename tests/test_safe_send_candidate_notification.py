from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage

from app.services.notifications import safe_send_candidate_notification
from tests.factories import make_full_chain


def _method() -> SendMessage:
    return SendMessage(chat_id=1, text="x")


@pytest.fixture
async def ctx(session):
    user, search, source, message, match = await make_full_chain(
        session,
        telegram_user_id=100,
        source_ref="ref-notif",
        message_text="Ищу помощника, звоните @ivan +7 900 123 45 67",
    )
    return session, user, search, source, message, match


async def test_skips_already_blocked_user(ctx):
    session, user, search, source, message, match = ctx
    user.is_blocked = True
    await session.flush()
    bot = AsyncMock()

    status = await safe_send_candidate_notification(
        bot,
        session,
        user=user,
        search=search,
        source=source,
        message=message,
        match=match,
    )

    assert status == "skipped_blocked"
    bot.send_message.assert_not_called()


async def test_successful_send_returns_sent(ctx):
    session, user, search, source, message, match = ctx
    bot = AsyncMock()

    status = await safe_send_candidate_notification(
        bot,
        session,
        user=user,
        search=search,
        source=source,
        message=message,
        match=match,
    )

    assert status == "sent"
    assert user.is_blocked is False
    bot.send_message.assert_awaited_once()


async def test_forbidden_error_marks_user_blocked(ctx):
    session, user, search, source, message, match = ctx
    bot = AsyncMock()
    bot.send_message.side_effect = TelegramForbiddenError(
        method=_method(),
        message="Forbidden: bot was blocked by the user",
    )

    status = await safe_send_candidate_notification(
        bot,
        session,
        user=user,
        search=search,
        source=source,
        message=message,
        match=match,
    )

    assert status == "blocked"
    assert user.is_blocked is True


async def test_bad_request_blocked_phrase_marks_user_blocked(ctx):
    session, user, search, source, message, match = ctx
    bot = AsyncMock()
    bot.send_message.side_effect = TelegramBadRequest(
        method=_method(),
        message="Bad Request: chat not found",
    )

    status = await safe_send_candidate_notification(
        bot,
        session,
        user=user,
        search=search,
        source=source,
        message=message,
        match=match,
    )

    assert status == "blocked"
    assert user.is_blocked is True


async def test_bad_request_unrelated_returns_failed(ctx):
    session, user, search, source, message, match = ctx
    bot = AsyncMock()
    bot.send_message.side_effect = TelegramBadRequest(
        method=_method(),
        message="Bad Request: message is too long",
    )

    status = await safe_send_candidate_notification(
        bot,
        session,
        user=user,
        search=search,
        source=source,
        message=message,
        match=match,
    )

    assert status == "failed"
    assert user.is_blocked is False


async def test_retry_after_then_success(ctx):
    session, user, search, source, message, match = ctx
    bot = AsyncMock()
    bot.send_message.side_effect = [
        TelegramRetryAfter(method=_method(), message="Too Many Requests", retry_after=0),
        None,
    ]

    status = await safe_send_candidate_notification(
        bot,
        session,
        user=user,
        search=search,
        source=source,
        message=message,
        match=match,
    )

    assert status == "sent"
    assert bot.send_message.await_count == 2


async def test_retry_after_twice_returns_failed(ctx):
    session, user, search, source, message, match = ctx
    bot = AsyncMock()
    bot.send_message.side_effect = TelegramRetryAfter(method=_method(), message="Too Many Requests", retry_after=0)

    status = await safe_send_candidate_notification(
        bot,
        session,
        user=user,
        search=search,
        source=source,
        message=message,
        match=match,
    )

    assert status == "failed"
    assert bot.send_message.await_count == 2
    assert user.is_blocked is False


async def test_generic_exception_returns_failed(ctx):
    session, user, search, source, message, match = ctx
    bot = AsyncMock()
    bot.send_message.side_effect = RuntimeError("network blip")

    status = await safe_send_candidate_notification(
        bot,
        session,
        user=user,
        search=search,
        source=source,
        message=message,
        match=match,
    )

    assert status == "failed"
    assert user.is_blocked is False
