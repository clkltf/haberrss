"""Optional Telegram public-channel signal collector.

Uses Telethon (MTProto) and listens to configured public channels. It does not
publish, join private groups, or bypass access controls. Credentials stay in
.env and must never be committed.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from datetime import datetime, timezone

from telethon import TelegramClient, events

log = logging.getLogger("haberrss.telegram_signal")

API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION = os.environ.get("TELEGRAM_SESSION", "haberrss")
CHANNELS = [x.strip() for x in os.environ.get("TELEGRAM_CHANNELS", "").split(",") if x.strip()]
KEYWORDS = [x.strip().lower() for x in os.environ.get("TELEGRAM_KEYWORDS", "son dakika,son gelişme,flaş,acil,deprem,patlama,yangın,kaza,tutuklandı,gözaltı,istifa").split(",") if x.strip()]


def fingerprint(channel: str, message_id: int, text: str) -> str:
    raw = f"telegram|{channel}|{message_id}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def relevant(text: str) -> bool:
    value = (text or "").lower()
    return any(k in value for k in KEYWORDS)


async def run() -> None:
    if not API_ID or not API_HASH or not CHANNELS:
        log.warning("Telegram signal collector disabled: configure TELEGRAM_API_ID, TELEGRAM_API_HASH and TELEGRAM_CHANNELS")
        return

    client = TelegramClient(SESSION, API_ID, API_HASH)

    @client.on(events.NewMessage(chats=CHANNELS))
    async def handler(event):
        text = event.raw_text or ""
        if not relevant(text):
            return
        chat = await event.get_chat()
        username = getattr(chat, "username", None)
        channel = f"@{username}" if username else str(getattr(chat, "id", "unknown"))
        payload = {
            "fingerprint": fingerprint(channel, event.id, text),
            "channel": channel,
            "message_id": event.id,
            "text": text[:4000],
            "published_at": (event.date or datetime.now(timezone.utc)).isoformat(),
        }
        # Structured log is intentionally the first integration point. The
        # next stage can persist this payload into Redis without changing the
        # Telegram listener.
        log.info("TELEGRAM_SIGNAL %s", payload)

    await client.start()
    log.info("Telegram signal collector listening channels=%s", CHANNELS)
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(run())
