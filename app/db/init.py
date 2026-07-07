import logging

from sqlalchemy import text

from app.db.models import Base
from app.db.session import engine

logger = logging.getLogger(__name__)

# Indexes that may be missing on databases created before the index was added
# to the model. Base.metadata.create_all() only creates missing tables, so an
# already-existing "users" table would not automatically get this index.
# CREATE INDEX IF NOT EXISTS makes this safe to run on every startup.
_EXTRA_INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS ix_users_is_blocked ON users (is_blocked)",
)


async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for statement in _EXTRA_INDEX_STATEMENTS:
            try:
                await conn.execute(text(statement))
            except Exception:
                logger.exception("Failed to ensure index: %s", statement)
