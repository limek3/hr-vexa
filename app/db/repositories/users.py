from aiogram.types import User as TelegramUser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_or_create_user(session: AsyncSession, telegram_user: TelegramUser) -> User:
    result = await session.execute(
        select(User).where(User.telegram_user_id == telegram_user.id),
    )
    user = result.scalar_one_or_none()
    if user:
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        user.is_blocked = False
        return user

    user = User(
        telegram_user_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
    )
    session.add(user)
    await session.flush()
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_user_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_user_id == telegram_user_id))
    return result.scalar_one_or_none()


async def count_blocked_users(session: AsyncSession) -> int:
    total = await session.scalar(
        select(func.count(User.id)).where(User.is_blocked.is_(True)),
    )
    return int(total or 0)


async def list_blocked_users(session: AsyncSession, *, limit: int = 10) -> list[User]:
    result = await session.execute(
        select(User)
        .where(User.is_blocked.is_(True))
        .order_by(User.updated_at.desc())
        .limit(limit),
    )
    return list(result.scalars().all())
