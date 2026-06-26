from aiogram.types import User as TelegramUser
from sqlalchemy import select
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
        return user

    user = User(
        telegram_user_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
    )
    session.add(user)
    await session.flush()
    return user
