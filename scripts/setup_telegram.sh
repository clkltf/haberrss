#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_FILE=.env
[ -f "$ENV_FILE" ] || touch "$ENV_FILE"
chmod 600 "$ENV_FILE"
setenv(){ grep -v "^$1=" "$ENV_FILE" > "$ENV_FILE.tmp" || true; printf '%s=%s\n' "$1" "$2" >> "$ENV_FILE.tmp"; mv "$ENV_FILE.tmp" "$ENV_FILE"; chmod 600 "$ENV_FILE"; }
read -rp 'Telegram API ID: ' API_ID
read -rsp 'Telegram API HASH: ' API_HASH; echo
read -rp 'Telegram phone (+90...): ' PHONE
read -rp 'Public channel usernames (comma separated, @ optional): ' CHANNELS
setenv TELEGRAM_API_ID "$API_ID"
setenv TELEGRAM_API_HASH "$API_HASH"
setenv TELEGRAM_PHONE "$PHONE"
setenv TELEGRAM_CHANNELS "$CHANNELS"
setenv TELEGRAM_SESSION "/data/telegram/haberrss"
setenv TELEGRAM_REDIS_STREAM "signals:telegram"
mkdir -p data/telegram
chmod 700 data/telegram
printf '\nTelegram credentials saved only in %s (chmod 600).\nStarting Telegram login container...\n' "$ENV_FILE"
docker compose run --rm telegram python -m haberrss.telegram_signal
