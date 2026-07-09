import logging

from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
from telethon.tl.types import ChatInviteAlready

from app.core.config import get_settings
from app.db.models import Source

logger = logging.getLogger(__name__)


def _invite_hash(input_ref: str) -> str | None:
    if "t.me/+" not in input_ref:
        return None
    return input_ref.rsplit("+", maxsplit=1)[-1].strip("/")


def _source_type(entity: object) -> str:
    if getattr(entity, "broadcast", False):
        return "channel"
    if getattr(entity, "megagroup", False):
        return "supergroup"
    if getattr(entity, "gigagroup", False):
        return "gigagroup"
    return "chat"


def _rpc_status(exc: RPCError) -> str:
    name = exc.__class__.__name__.casefold()
    if "flood" in name:
        return "join_limited"
    if "expired" in name or "invalid" in name:
        return "invite_expired"
    if "request" in name:
        return "join_request_sent"
    if "private" in name or "forbidden" in name:
        return "unavailable"
    return "unavailable"


def _chat_from_updates(updates: object) -> object | None:
    chats = getattr(updates, "chats", None) or []
    return chats[0] if chats else None


def _access_result(
    telegram_id: int | None,
    title: str,
    source_type: str,
    access_status: str,
    entity: object | None = None,
) -> tuple[int | None, str, str, str, tuple[int, str, str] | None, object | None]:
    return telegram_id, title, source_type, access_status, None, entity


async def _join_invite_source(
    client: TelegramClient,
    invite_hash: str,
    *,
    allow_join: bool,
) -> object | None:
    checked = await client(CheckChatInviteRequest(invite_hash))
    if isinstance(checked, ChatInviteAlready):
        return checked.chat

    if not allow_join or not get_settings().telegram_auto_join_sources:
        return None

    updates = await client(ImportChatInviteRequest(invite_hash))
    return _chat_from_updates(updates)


async def _join_public_source_if_needed(
    client: TelegramClient,
    entity: object,
    *,
    allow_join: bool,
) -> object:
    if not getattr(entity, "left", False):
        return entity

    if not allow_join or not get_settings().telegram_auto_join_sources:
        return entity

    updates = await client(JoinChannelRequest(entity))
    return _chat_from_updates(updates) or entity


async def resolve_source_access(
    client: TelegramClient,
    source: Source,
    *,
    allow_join: bool = True,
) -> tuple[int | None, str, str, str, tuple[int, str, str] | None, object | None]:
    try:
        invite_hash = _invite_hash(source.input_ref)
        if invite_hash:
            entity = await _join_invite_source(client, invite_hash, allow_join=allow_join)
            if entity is None:
                access_status = "queued" if get_settings().telegram_auto_join_sources else "unavailable"
                logger.info("Invite source is %s: %s", access_status, source.input_ref)
                return _access_result(
                    source.telegram_id,
                    source.title or source.input_ref,
                    source.type,
                    access_status,
                )
        else:
            entity = await client.get_entity(source.input_ref)
            entity = await _join_public_source_if_needed(client, entity, allow_join=allow_join)
            if getattr(entity, "left", False):
                access_status = "queued" if get_settings().telegram_auto_join_sources else "unavailable"
                logger.info("Source is %s: %s", access_status, source.input_ref)
                return _access_result(
                    source.telegram_id,
                    getattr(entity, "title", None) or source.input_ref,
                    _source_type(entity),
                    access_status,
                    entity,
                )

        telegram_id = getattr(entity, "id", None)
        title = getattr(entity, "title", None) or source.input_ref
        return _access_result(telegram_id, title, _source_type(entity), "available", entity)
    except RPCError as exc:
        logger.warning("Source unavailable %s: %s", source.input_ref, exc)
        return _access_result(
            source.telegram_id,
            source.title or source.input_ref,
            source.type,
            _rpc_status(exc),
        )
    except ValueError as exc:
        logger.warning("Source not found %s: %s", source.input_ref, exc)
        return _access_result(
            source.telegram_id,
            source.title or source.input_ref,
            source.type,
            "not_found",
        )
