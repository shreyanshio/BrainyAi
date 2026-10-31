#!/usr/bin/env bash
# Dual-runner for Render.com free tier:
# Starts both the Telegram Bot worker and Gunicorn Flask web server in a single service.

set -e

echo "[Render Startup] Starting BrainyAi combined services..."

# Start Telegram Bot in background if TELEGRAM_TOKEN or TELEGRAM_BOT_TOKEN is provided
TG_TOKEN="${TELEGRAM_TOKEN:-$TELEGRAM_BOT_TOKEN}"
if [ -n "$TG_TOKEN" ]; then
    export TELEGRAM_TOKEN="$TG_TOKEN"
    export TELEGRAM_BOT_TOKEN="$TG_TOKEN"
    echo "[Render Startup] Launching Telegram Bot (study_bot.py) in background..."
    python study_bot.py &
    BOT_PID=$!
    echo "[Render Startup] Telegram Bot PID: $BOT_PID"
else
    echo "[Render Startup] Neither TELEGRAM_TOKEN nor TELEGRAM_BOT_TOKEN set, skipping Telegram Bot."
fi

# Run Gunicorn in foreground binding to $PORT (Render passes PORT dynamically, default 10000)
PORT="${PORT:-10000}"
echo "[Render Startup] Launching Gunicorn web server on 0.0.0.0:$PORT..."
exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
