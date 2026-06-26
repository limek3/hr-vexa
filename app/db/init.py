from app.db.models import Base
from app.db.session import engine


async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
