import logging

from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.functions.messages import CheckChatInviteRequest
from telethon.tl.types import ChatInviteAlready

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


async def resolve_source_access(
    client: TelegramClient,
    source: Source,
) -> tuple[int | None, str, str, str, tuple[int, str, str] | None]:
    try:
        invite_hash = _invite_hash(source.input_ref)
        if invite_hash:
            checked = await client(CheckChatInviteRequest(invite_hash))
            if not isinstance(checked, ChatInviteAlready):
                logger.info("Invite source is not joined and auto-join is disabled: %s", source.input_ref)
                return source.telegram_id, source.title or source.input_ref, source.type, "unavailable", None
            entity = checked.chat
        else:
            entity = await client.get_entity(source.input_ref)
            if getattr(entity, "left", False):
                logger.info("Source is not joined and auto-join is disabled: %s", source.input_ref)
                return source.telegram_id, getattr(entity, "title", None) or source.input_ref, _source_type(entity), "unavailable", None

        telegram_id = getattr(entity, "id", None)
        title = getattr(entity, "title", None) or source.input_ref
        return telegram_id, title, _source_type(entity), "available", None
    except RPCError as exc:
        logger.warning("Source unavailable %s: %s", source.input_ref, exc)
        return source.telegram_id, source.title or source.input_ref, source.type, "unavailable", None
    except ValueError as exc:
        logger.warning("Source not found %s: %s", source.input_ref, exc)
        return source.telegram_id, source.title or source.input_ref, source.type, "not_found", None
