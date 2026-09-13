"""Free external early-signal collectors.

These sources complement publisher RSS. They are intentionally best-effort: a
failure never stops the main worker. GDELT is a broad news signal; Google
Trends is a public rising-interest signal. Neither is assumed to be second-
level realtime, so timestamps are kept explicit and scores remain signals,
not facts.
"""
import hashlib
import logging
import re
from datetime import datetime, timezone

import feedparser
import httpx
import psycopg

from .config import settings

log = logging.getLogger("haberrss.realtime")

TRENDS_URL = "https://trends.google.com/trendingsearches/daily/rss?geo=TR"
GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def _hash(title: str) -> str:
    s = re.sub(r"\s+", " ", title.lower()).strip()
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _source(conn, name: str, url: str, category: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO sources(name,url,category) VALUES(%s,%s,%s)
               ON CONFLICT(url) DO UPDATE SET name=EXCLUDED.name, category=EXCLUDED.category, active=TRUE
               RETURNING id""",
            (name, url, category),
        )
        return cur.fetchone()[0]


def _insert(conn, source_id: int, title: str, url: str, summary: str, published_at, category: str) -> int:
    if not title or not url:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO articles(source_id,title,url,summary,published_at,title_hash,category)
               VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(url) DO NOTHING""",
            (source_id, title[:1000], url, summary[:5000], published_at, _hash(title), category),
        )
        return cur.rowcount


def collect_google_trends(conn) -> int:
    source_id = _source(conn, "Google Trends Türkiye", TRENDS_URL, "trend-signal")
    feed = feedparser.parse(TRENDS_URL)
    count = 0
    now = datetime.now(timezone.utc)
    for e in getattr(feed, "entries", [])[:100]:
        title = re.sub(r"\s+", " ", getattr(e, "title", "")).strip()
        link = getattr(e, "link", "").strip()
        summary = re.sub(r"<[^>]+>", " ", getattr(e, "summary", ""))
        count += _insert(conn, source_id, f"[TREND] {title}", link or TRENDS_URL, summary, now, "trend-signal")
    conn.commit()
    return count


def collect_gdelt(conn) -> int:
    source_url = GDELT_URL + "?query=Turkey&mode=artlist&maxrecords=100&format=json&timespan=15m"
    source_id = _source(conn, "GDELT Turkey 15m", source_url, "gdelt")
    count = 0
    try:
        with httpx.Client(timeout=settings.source_timeout_seconds, follow_redirects=True) as client:
            r = client.get(GDELT_URL, params={"query": "Turkey", "mode": "artlist", "maxrecords": 100, "format": "json", "timespan": "15m"})
            r.raise_for_status()
            data = r.json()
        for item in data.get("articles", []):
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            domain = str(item.get("domain") or "GDELT")
            ts = item.get("seendate")
            published = None
            if ts:
                try:
                    published = datetime.strptime(ts[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
            count += _insert(conn, source_id, title, url, domain, published, "gdelt")
        conn.commit()
    except Exception:
        conn.rollback()
        log.exception("GDELT collector failed")
    return count


def collect_early_signals() -> int:
    conn = psycopg.connect(settings.database_url)
    try:
        total = 0
        try:
            total += collect_gdelt(conn)
        except Exception:
            conn.rollback(); log.exception("GDELT signal failed")
        try:
            total += collect_google_trends(conn)
        except Exception:
            conn.rollback(); log.exception("Google Trends signal failed")
        return total
    finally:
        conn.close()
