# lex-tg Railway Deployment Guide

This guide will help you deploy **lex-tg** to [Railway.app](https://railway.app) using Docker and a PostgreSQL database.

## 1. Create a New Project
1. Go to [Railway Dashboard](https://railway.app/dashboard).
2. Click **New Project** -> **Deploy from GitHub Repo**.
3. Select your `lex-tg` repository.

## 2. Add PostgreSQL Database
1. In your Railway project canvas, click **New** -> **Database** -> **Add PostgreSQL**.
2. Railway will automatically create a `DATABASE_URL` variable for the project.

## 3. Configure the Bot Service
1. Click on your bot service.
2. Go to the **Variables** tab and add the following:
   *   `API_ID`: Your Telegram API ID.
   *   `API_HASH`: Your Telegram API Hash.
   *   `BOT_TOKEN`: Your Telegram Bot Token.
   *   `OWNER_ID`: Your Telegram User ID.
   *   `DATABASE_URL`: Set this to `${{Postgres.DATABASE_URL}}` (Railway automatically links it).
   *   `LOG_LEVEL`: `INFO`
   *   `ENABLE_VIDEO_WATERMARK`: `True` or `False`.
   *   `VIDEO_WATERMARK_MAX_SIZE_MB`: E.g., `20`.

## 4. Setup Persistent Sessions & Data (CRITICAL)
Railway's filesystem is ephemeral. To prevent data loss and repeated log-ins:
1. Go to your bot service -> **Settings**.
2. Scroll to **Volumes** -> **Add Volume**.
3. Create volumes for the following paths:
   *   Mount Path: `/app/sessions` (For Telegram sessions)
   *   Mount Path: `/app/data` (For local cache snapshots)
   *   Mount Path: `/app/logs` (Optional, for persistent logs)

## 5. Deployment
1. Every time you push to GitHub, Railway will build the Docker container and deploy it.
2. Check the **Logs** tab to verify the `lex-tg is running!` message appears.

---

### Troubleshooting
- **Database Connection**: Ensure `DATABASE_URL` uses the `${{Postgres.DATABASE_URL}}` reference.
- **Session Reset**: If the bot asks to log in again after a restart, ensure the volume is correctly mounted to `/app/sessions`.
- **Migrations**: The bot automatically runs `alembic upgrade head` on startup. check the logs if you see migration errors.
