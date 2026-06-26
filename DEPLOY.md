# Deploy Vexa to Railway

## 1. Push Code to GitHub

```bash
git add .
git commit -m "Update Vexa"
git push
```

If GitHub remote is wrong:

```bash
git remote set-url origin https://github.com/YOUR_USERNAME/hr-vexa.git
git push -u origin main
```

## 2. Create Railway Service

1. Open Railway.
2. New Project.
3. GitHub Repository.
4. Select the `hr-vexa` repository.
5. Railway will use `railway.json`.

Start command:

```bash
python -m app.worker.main
```

## 3. Add Variables

Add these variables to the Railway service:

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

## 4. Keep One Service

Use only one Railway service for this project.

If you have both `hrvexa-bot` and `hrvexa-monitor`, delete one of them. Running two services with the same `BOT_TOKEN` causes:

```text
Conflict: terminated by other getUpdates request
```

## 5. Check Logs

Healthy logs:

```text
Starting combined worker: bot + monitor
Bot polling started
Run polling for bot @hrvexa_bot
MTProto monitor started as ...
```
