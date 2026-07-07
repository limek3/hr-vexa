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
ADMIN_TELEGRAM_IDS=
NOTIFICATION_DELIVERY_RETENTION_DAYS=30
```

`TELEGRAM_AUTO_JOIN_SOURCES=true` lets the MTProto monitor join public sources and
`https://t.me/+...` invite links when the connected Telegram account is allowed to join.
`TELEGRAM_MAX_JOINS_PER_CYCLE=2` and `TELEGRAM_JOIN_DELAY_SECONDS=12` keep joins in a
small queue so the account does not try to join many sources at once.
`MAX_SOURCES_PER_SEARCH=10` keeps one search limited to 10 sources.
`ADMIN_TELEGRAM_IDS` is a comma-separated list of Telegram user IDs allowed to use the
`/unblock` and `/blocked_count` admin bot commands (see "Blocked Bot Users" below). Leave it
empty to disable both commands.
`NOTIFICATION_DELIVERY_RETENTION_DAYS` controls how long terminal (`blocked`/`failed`)
notification delivery records are kept before an automatic cleanup job removes them;
`sent` records are never auto-deleted.

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

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Repository and notification-delivery tests run against an in-memory SQLite database, so no
`DATABASE_URL` is needed to run the suite.

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

## Blocked Bot Users

If a user blocks the bot, Telegram raises `TelegramForbiddenError` (or a `TelegramBadRequest`
containing "chat not found" / "user is deactivated" / "bot was blocked") when the bot tries to
message them. The bot catches these errors, marks the user as blocked in the database, and skips
sending further notifications to them. Matches and stats keep being saved as usual; only outgoing
Telegram messages are skipped. A transient Telegram flood-control response
(`TelegramRetryAfter`) is treated separately: the bot waits out the requested delay once and
retries, instead of marking the user as blocked.

To see which users currently have the bot blocked:

```sql
select id, telegram_user_id, username, first_name, is_blocked, updated_at
from users
where is_blocked = true
order by updated_at desc;
```

When a user writes to the bot again, `is_blocked` is reset to false. An admin can also reset it
manually (for example, right after confirming with the user that they unblocked the bot).

### Admin panel

Set `ADMIN_TELEGRAM_IDS` (see above) and send `/admin` from one of those Telegram accounts to
open an inline-button panel, visible and usable only by those accounts:

- **Заблокировавшие бота** — the most recent blocked users (up to 10), each with its own
  **Разблокировать** button; tapping it resets `is_blocked` to false for that user and refreshes
  the list in place.
- **Общая статистика** — instance-wide numbers: total/blocked users, total/active searches,
  total sources, matches today and all-time.
- **Обновить** — redraws the panel.

Non-admins who somehow send `/admin` or one of the `admin:...` callback buttons get no response;
the panel is not linked from the regular user menu.

The same actions are also available as plain text commands, for scripting or when a button isn't
convenient:

- `/unblock <telegram_user_id>` — resets `is_blocked` to false for that user.
- `/blocked_count` — replies with the current count of users who have the bot blocked.

The monitor also sends this same count once a day directly to every ID in `ADMIN_TELEGRAM_IDS`
as a Telegram message (in addition to logging `Blocked users report: total_blocked=...`). If an
admin has blocked the bot themselves, or the admin ID is invalid, that failure is only logged
(`Blocked users report: failed to notify admin...`) and does not affect the other admins or the
rest of the monitor.

Old terminal delivery records (`status` = `blocked` or `failed`) older than
`NOTIFICATION_DELIVERY_RETENTION_DAYS` are cleaned up automatically once a day; `sent` records
are kept indefinitely for audit purposes.

## MVP Scope

- Keyword and minus-word matching.
- New messages only.
- Telegram UI only.
- No AI matching.
- No CRM pipeline.
- No web dashboard yet.
