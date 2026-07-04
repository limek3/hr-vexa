# Vexa

Telegram-monitoring bot for keyword-based tracking across channels, groups, posts, and comments.

Vexa lets a user create keyword searches, attach Telegram sources, and receive new matching messages directly in Telegram.

## Current Architecture

```text
Railway worker
  -> Telegram Bot UI
  -> MTProto monitor
  -> Supabase Postgres
```

The project is deployed as one Railway service:

```bash
python -m app.worker.main
```

This single command starts both the bot interface and the MTProto monitor.

## Environment Variables

Required on Railway:

```env
BOT_TOKEN=
DATABASE_URL=
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_SESSION_STRING=
TELEGRAM_AUTO_JOIN_SOURCES=true
TELEGRAM_SOURCE_REFRESH_INTERVAL_SECONDS=60
TELEGRAM_JOIN_DELAY_SECONDS=12
TELEGRAM_MAX_JOINS_PER_CYCLE=2
MAX_SOURCES_PER_SEARCH=10
APP_ENV=production
LOG_LEVEL=INFO
```

Optional:

```env
BOT_PROXY_URL=
```

`TELEGRAM_AUTO_JOIN_SOURCES=true` lets the MTProto monitor join public sources and
`https://t.me/+...` invite links when the connected Telegram account is allowed to join.
`TELEGRAM_MAX_JOINS_PER_CYCLE=2` and `TELEGRAM_JOIN_DELAY_SECONDS=12` keep joins in a
small queue so the account does not try to join many sources at once.
`MAX_SOURCES_PER_SEARCH=10` keeps one search limited to 10 sources.

Use Supabase Session Pooler for `DATABASE_URL` if direct connection does not work from your network.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Create MTProto Session

```bash
python -m app.monitor.login_qr
```

Scan the QR code from Telegram:

```text
Settings -> Devices -> Link Desktop Device
```

Copy the printed value into `TELEGRAM_SESSION_STRING`.

## Run Locally

Run the combined worker:

```bash
python -m app.worker.main
```

Or run parts separately:

```bash
python -m app.bot.main
python -m app.monitor.main
```

## Railway Deploy

Railway reads `railway.json`:

```json
{
  "deploy": {
    "startCommand": "python -m app.worker.main"
  }
}
```

Use one service only. Do not create a second service with the same bot token, otherwise Telegram will return a `getUpdates` conflict.

## MVP Scope

- Keyword and minus-word matching.
- New messages only.
- Telegram UI only.
- No AI matching.
- No CRM pipeline.
- No web dashboard yet.
