import logging

from telethon import TelegramClient
from telethon.errors import RPCError, UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

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


async def resolve_and_join_source(client: TelegramClient, source: Source) -> tuple[int | None, str, str, str]:
    try:
        invite_hash = _invite_hash(source.input_ref)
        if invite_hash:
            try:
                updates = await client(ImportChatInviteRequest(invite_hash))
                chats = getattr(updates, "chats", [])
                entity = chats[0] if chats else await client.get_entity(source.input_ref)
            except UserAlreadyParticipantError:
                entity = await client.get_entity(source.input_ref)
        else:
            entity = await client.get_entity(source.input_ref)
            try:
                await client(JoinChannelRequest(entity))
            except UserAlreadyParticipantError:
                pass
            except RPCError as exc:
                logger.info("Could not join %s: %s", source.input_ref, exc)

        telegram_id = getattr(entity, "id", None)
        title = getattr(entity, "title", None) or source.input_ref
        return telegram_id, title, _source_type(entity), "available"
    except RPCError as exc:
        logger.warning("Source unavailable %s: %s", source.input_ref, exc)
        return source.telegram_id, source.title or source.input_ref, source.type, "unavailable"
    except ValueError as exc:
        logger.warning("Source not found %s: %s", source.input_ref, exc)
        return source.telegram_id, source.title or source.input_ref, source.type, "not_found"
