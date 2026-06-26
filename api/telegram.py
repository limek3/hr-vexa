from fastapi import FastAPI, Header, HTTPException, Request

from aiogram.types import Update

from app.bot.client import create_bot
from app.bot.factory import create_dispatcher
from app.core.config import get_settings

settings = get_settings()
app = FastAPI()


@app.post("/api/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

    if not settings.bot_token:
        raise HTTPException(status_code=500, detail="BOT_TOKEN is not configured")

    payload = await request.json()
    bot = create_bot(settings.bot_token, settings.bot_proxy_url)
    dp = create_dispatcher()
    update = Update.model_validate(payload, context={"bot": bot})
    await dp.feed_update(bot, update)
    await bot.session.close()
    return {"ok": True}
