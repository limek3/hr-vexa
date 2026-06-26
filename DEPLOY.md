# Deploy Checklist

## Supabase

1. Create a Supabase project.
2. Open Project Settings -> Database -> Connect.
3. Copy the Postgres connection string.
4. Put it into `DATABASE_URL`.

For the always-on monitor worker, prefer direct connection or session pooler.

## Telegram Bot

1. Create bot in BotFather.
2. Copy token to `BOT_TOKEN`.
3. Set bot name, about text and description.

## MTProto

1. Put `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` into `.env`.
2. Run locally:

```bash
python -m app.monitor.login
```

3. Copy printed `TELEGRAM_SESSION_STRING`.

## Vercel

Use Vercel for the bot webhook only.

Required env:

```env
BOT_TOKEN=
DATABASE_URL=
TELEGRAM_WEBHOOK_SECRET=
```

Set webhook:

```bash
curl "https://api.telegram.org/bot$BOT_TOKEN/setWebhook?url=https://YOUR_DOMAIN.vercel.app/api/telegram&secret_token=$TELEGRAM_WEBHOOK_SECRET"
```

## Worker Hosting

Use Render, Railway, Fly.io or VPS for:

```bash
python -m app.monitor.main
```

Required env:

```env
BOT_TOKEN=
DATABASE_URL=
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_SESSION_STRING=
```
