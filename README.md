# Recruit Radar

Telegram recruiting MVP:

- Telegram bot interface for HR users.
- Supabase Postgres database.
- MTProto monitor-worker for Telegram sources.
- Optional Vercel webhook endpoint for the bot.

## Architecture

```text
Telegram Bot UI
  -> Vercel webhook or local polling
  -> Supabase Postgres

MTProto monitor-worker
  -> Render / Railway / Fly.io / VPS
  -> Supabase Postgres
  -> Telegram sources
  -> bot notifications
```

Vercel is good for the bot webhook, but the MTProto monitor is a long-running process and should run on an always-on worker platform.

## Environment

Copy:

```bash
cp .env.example .env
```

Fill in:

```env
BOT_TOKEN=
DATABASE_URL=
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_SESSION_STRING=
TELEGRAM_WEBHOOK_SECRET=
```

For Supabase, use the Postgres connection string from Project Settings -> Database -> Connect.
For a persistent worker, direct connection or session pooler is preferred.

## Install Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Create Tables

For the MVP, the bot and monitor auto-create tables on startup.
For a stricter production flow, use Alembic migrations later.

## Create MTProto Session String

Run once locally:

```bash
python -m app.monitor.login
```

Telegram will ask for:

- phone number;
- login code;
- 2FA password, if enabled.

The command prints:

```env
TELEGRAM_SESSION_STRING=...
```

Put that value into your hosting environment variables. Do not publish it.

## Run Locally

Terminal 1:

```bash
python -m app.bot.main
```

Terminal 2:

```bash
python -m app.monitor.main
```

Local bot mode uses polling. For production on Vercel, use webhook mode.

## Vercel Bot Webhook

This project includes:

```text
api/telegram.py
```

Deploy the repo to Vercel and add environment variables:

```env
BOT_TOKEN=
DATABASE_URL=
TELEGRAM_WEBHOOK_SECRET=
```

Then set the Telegram webhook:

```bash
curl "https://api.telegram.org/bot$BOT_TOKEN/setWebhook?url=https://YOUR_DOMAIN.vercel.app/api/telegram&secret_token=$TELEGRAM_WEBHOOK_SECRET"
```

## Monitor Worker

Deploy this command to an always-on Python worker:

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

Good hosting choices:

- Render worker
- Railway worker
- Fly.io machine
- small VPS

## Render Deploy

This repository includes `render.yaml` with two background workers:

- `hrvexa-bot`: Telegram Bot API polling process.
- `hrvexa-monitor`: MTProto monitor process.

Set secret environment variables in Render manually. Do not commit `.env`.

## Railway Deploy

Railway uses `railway.json` and starts one combined worker:

```bash
python -m app.worker.main
```

This single process runs both:

- Telegram Bot API polling;
- MTProto monitor-worker.

Required environment variables:

```env
BOT_TOKEN=
DATABASE_URL=
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_SESSION_STRING=
APP_ENV=production
LOG_LEVEL=INFO
```

## MVP Limits

- No AI matching.
- No CRM.
- No history parsing.
- No web dashboard yet.
- No billing yet.
