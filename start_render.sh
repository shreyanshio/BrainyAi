#!/usr/bin/env bash
# Dual-runner for Render.com free tier:
# Starts both the Telegram Bot worker and Gunicorn Flask web server in a single service.

set -e

echo "[Render Startup] Starting BrainyAi combined services..."

# Start Telegram Bot in background if TELEGRAM_BOT_TOKEN is provided
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    echo "[Render Startup] Launching Telegram Bot (study_bot.py) in background..."
    python study_bot.py &
    BOT_PID=$!
    echo "[Render Startup] Telegram Bot PID: $BOT_PID"
else
    echo "[Render Startup] TELEGRAM_BOT_TOKEN not set, skipping Telegram Bot."
fi

# Run Gunicorn in foreground binding to $PORT (Render passes PORT dynamically, default 10000)
PORT="${PORT:-10000}"
echo "[Render Startup] Launching Gunicorn web server on 0.0.0.0:$PORT..."
exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
