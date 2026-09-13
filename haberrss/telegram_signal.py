from __future__ import annotations
import asyncio, hashlib, logging, os, re
from datetime import datetime, timezone
import psycopg
import redis.asyncio as redis
from telethon import TelegramClient, events

log = logging.getLogger("haberrss.telegram")
API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION = os.environ.get("TELEGRAM_SESSION", "/data/telegram/haberrss")
CHANNELS = [x.strip() for x in os.environ.get("TELEGRAM_CHANNELS", "").split(",") if x.strip()]
KEYWORDS = [x.strip().lower() for x in os.environ.get("TELEGRAM_KEYWORDS", "son dakika,son gelişme,flaş,acil,deprem,sarsıntı,patlama,yangın,kaza,tutuklandı,gözaltı,istifa,ölü,yaralı,maç,gol,transfer,zam,karar").split(",") if x.strip()]
DATABASE_URL = os.environ.get("DATABASE_URL", "")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
STREAM = os.environ.get("TELEGRAM_REDIS_STREAM", "signals:telegram")

def clean(text): return re.sub(r"\s+", " ", text or "").strip()
def title_hash(title): return hashlib.sha256(re.sub(r"\s+", " ", re.sub(r"[^a-z0-9çğıöşü ]", "", title.lower())).strip().encode()).hexdigest()
def relevant(text): return any(k in text.lower() for k in KEYWORDS)
def make_title(text): return clean(text).split(" | ")[0][:300] or "Telegram sinyali"

async def main():
    if not API_ID or not API_HASH or not CHANNELS or not DATABASE_URL:
        log.error("Telegram disabled: required credentials/config missing")
        return
    r = redis.from_url(REDIS_URL, decode_responses=True)
    client = TelegramClient(SESSION, API_ID, API_HASH)
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for channel in CHANNELS:
                cur.execute("INSERT INTO sources (name,url,category) VALUES (%s,%s,'telegram') ON CONFLICT (url) DO UPDATE SET active=TRUE", (f"Telegram {channel}", f"telegram://{channel.lstrip('@')}"))
        conn.commit()

    @client.on(events.NewMessage(chats=CHANNELS))
    async def handler(event):
        text = clean(event.raw_text)
        if not text or not relevant(text): return
        chat = await event.get_chat(); username = getattr(chat, "username", None)
        channel = f"@{username}" if username else str(getattr(chat, "id", "unknown"))
        published = event.date or datetime.now(timezone.utc)
        url = f"https://t.me/{username}/{event.id}" if username else f"telegram://{getattr(chat, 'id', 'unknown')}/{event.id}"
        title = make_title(text)
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM sources WHERE url=%s", (f"telegram://{channel.lstrip('@')}",))
                row = cur.fetchone(); source_id = row[0] if row else None
                cur.execute("""INSERT INTO articles (source_id,title,url,summary,published_at,title_hash,category,language,status) VALUES (%s,%s,%s,%s,%s,%s,'telegram','tr','new') ON CONFLICT (url) DO NOTHING RETURNING id""", (source_id,title,url,text[:10000],published,title_hash(title)))
                inserted = cur.fetchone()
            conn.commit()
        payload = {"channel":channel,"message_id":event.id,"title":title,"text":text[:10000],"url":url,"published_at":published.isoformat(),"article_id":inserted[0] if inserted else None}
        await r.xadd(STREAM, payload, maxlen=50000, approximate=True)
        log.info("TELEGRAM_SIGNAL channel=%s message=%s article_id=%s", channel,event.id,payload["article_id"])

    await client.start()
    log.info("Telegram listener active channels=%s stream=%s", CHANNELS, STREAM)
    try: await client.run_until_disconnected()
    finally: await r.aclose()

if __name__ == "__main__": asyncio.run(main())
