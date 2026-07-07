# NOTE: the project targets Python >=3.11 (see pyproject.toml) and uses
# `from datetime import UTC` in several modules. This shim only exists so
# the test suite can also run in CI/sandbox environments stuck on 3.10; it
# has no effect on 3.11+ where datetime.UTC already exists.
import datetime as _datetime

if not hasattr(_datetime, "UTC"):
    _datetime.UTC = _datetime.timezone.utc

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base


@pytest_asyncio.fixture
async def session():
    """In-memory SQLite session with all tables created, for repository/service tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db_session:
        yield db_session

    await engine.dispose()
