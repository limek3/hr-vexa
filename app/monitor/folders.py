import logging

from telethon import TelegramClient, utils
from telethon.errors import RPCError
from telethon.tl.functions.messages import GetDialogFiltersRequest, UpdateDialogFilterRequest
from telethon.tl.types import DialogFilter

from app.core.config import get_settings
from app.db.models import Source

logger = logging.getLogger(__name__)

MAX_FOLDER_INCLUDE_PEERS = 200


def _dialog_filter_title(dialog_filter: object) -> str:
    title = getattr(dialog_filter, "title", "")
    return getattr(title, "text", title) or ""


def _peer_key(peer: object) -> int | str:
    try:
        return utils.get_peer_id(peer)
    except Exception:
        return repr(peer)


def _find_dialog_filter(filters: list[object], title: str) -> object | None:
    normalized_title = title.casefold()
    for dialog_filter in filters:
        if not hasattr(dialog_filter, "id") or not hasattr(dialog_filter, "include_peers"):
            continue
        if _dialog_filter_title(dialog_filter).casefold() == normalized_title:
            return dialog_filter
    return None


def _next_dialog_filter_id(filters: list[object]) -> int:
    used_ids = {getattr(dialog_filter, "id", None) for dialog_filter in filters}
    for folder_id in range(2, 256):
        if folder_id not in used_ids:
            return folder_id
    raise RuntimeError("Telegram dialog folder limit reached")


async def add_source_to_telegram_folder(
    client: TelegramClient,
    entity: object | None,
    *,
    source: Source,
) -> str:
    """Add an available source to the configured Telegram dialog folder.

    Telegram folders belong to the MTProto account connected through
    TELEGRAM_SESSION_STRING. Bot API users do not have their own folders changed.
    """
    settings = get_settings()
    folder_title = settings.telegram_sources_folder_title.strip()
    if not folder_title:
        return "disabled"
    if entity is None:
        logger.info(
            "Telegram sources folder sync skipped, source entity is missing: "
            "source_id=%s input_ref=%s",
            source.id,
            source.input_ref,
        )
        return "entity_missing"

    try:
        input_peer = await client.get_input_entity(entity)
        filters = list(await client(GetDialogFiltersRequest()))
        dialog_filter = _find_dialog_filter(filters, folder_title)
        if dialog_filter is None:
            available_titles = [
                _dialog_filter_title(item)
                for item in filters
                if hasattr(item, "id") and hasattr(item, "include_peers")
            ]
            if not settings.telegram_sources_folder_create_if_missing:
                logger.warning(
                    "Telegram sources folder not found: folder_title=%s source_id=%s input_ref=%s "
                    "available_folders=%s",
                    folder_title,
                    source.id,
                    source.input_ref,
                    available_titles,
                )
                return "folder_missing"

            folder_id = _next_dialog_filter_id(filters)
            dialog_filter = DialogFilter(
                id=folder_id,
                title=folder_title,
                pinned_peers=[],
                include_peers=[input_peer],
                exclude_peers=[],
            )
            await client(UpdateDialogFilterRequest(id=folder_id, filter=dialog_filter))
            logger.info(
                "Telegram sources folder created and source added: folder_title=%s folder_id=%s "
                "source_id=%s telegram_id=%s",
                folder_title,
                folder_id,
                source.id,
                source.telegram_id,
            )
            return "created"

        include_peers = list(getattr(dialog_filter, "include_peers", None) or [])
        input_peer_key = _peer_key(input_peer)
        if any(_peer_key(peer) == input_peer_key for peer in include_peers):
            logger.debug(
                "Telegram sources folder already contains source: folder_title=%s folder_id=%s "
                "source_id=%s telegram_id=%s",
                folder_title,
                dialog_filter.id,
                source.id,
                source.telegram_id,
            )
            return "already_present"

        if len(include_peers) >= MAX_FOLDER_INCLUDE_PEERS:
            logger.warning(
                "Telegram sources folder is full: folder_title=%s folder_id=%s source_id=%s "
                "current_peers=%s",
                folder_title,
                dialog_filter.id,
                source.id,
                len(include_peers),
            )
            return "folder_full"

        dialog_filter.include_peers = [*include_peers, input_peer]
        await client(UpdateDialogFilterRequest(id=dialog_filter.id, filter=dialog_filter))
        logger.info(
            "Telegram source added to folder: folder_title=%s folder_id=%s source_id=%s "
            "telegram_id=%s",
            folder_title,
            dialog_filter.id,
            source.id,
            source.telegram_id,
        )
        return "added"
    except RPCError as exc:
        logger.warning(
            "Telegram sources folder sync failed: folder_title=%s source_id=%s "
            "input_ref=%s error=%s",
            folder_title,
            source.id,
            source.input_ref,
            exc,
        )
        return "failed"
    except Exception:
        logger.exception(
            "Telegram sources folder sync failed unexpectedly: folder_title=%s "
            "source_id=%s input_ref=%s",
            folder_title,
            source.id,
            source.input_ref,
        )
        return "failed"
