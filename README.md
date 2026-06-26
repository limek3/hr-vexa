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
APP_ENV=production
LOG_LEVEL=INFO
```

Optional:

```env
BOT_PROXY_URL=
```

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
