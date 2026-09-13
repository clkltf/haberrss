"""Free external early-signal collectors.

Best-effort collectors complement publisher RSS. A failure in one external
source must never stop the main worker. GDELT is treated as a discovery signal,
not as a source of truth.
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
GDELT_QUERY = '(Turkey OR Türkiye OR Istanbul OR Ankara)'


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
    log.info("Google Trends collected=%s", count)
    return count


def collect_gdelt(conn) -> int:
    source_url = GDELT_URL + "?query=" + GDELT_QUERY + "&mode=artlist&maxrecords=100&format=json&timespan=15m&sort=datedesc"
    source_id = _source(conn, "GDELT Turkey 15m", source_url, "gdelt")
    params = {
        "query": GDELT_QUERY,
        "mode": "artlist",
        "maxrecords": 100,
        "format": "json",
        "timespan": "15m",
        "sort": "datedesc",
    }
    try:
        with httpx.Client(
            timeout=httpx.Timeout(settings.source_timeout_seconds, connect=min(settings.source_timeout_seconds, 5)),
            follow_redirects=True,
            headers={"User-Agent": "HaberRSS/1.0 (+news monitoring)"},
        ) as client:
            r = client.get(GDELT_URL, params=params)
            r.raise_for_status()
            content_type = r.headers.get("content-type", "")
            if "json" not in content_type.lower() and not r.text.lstrip().startswith("{"):
                raise RuntimeError(f"unexpected GDELT response content-type={content_type!r}")
            data = r.json()

        if not isinstance(data, dict):
            raise RuntimeError("GDELT response is not a JSON object")

        articles = data.get("articles") or []
        count = 0
        for item in articles:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            domain = str(item.get("domain") or "GDELT")
            ts = str(item.get("seendate") or "")
            published = None
            if len(ts) >= 14:
                try:
                    published = datetime.strptime(ts[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
            count += _insert(conn, source_id, title, url, domain, published, "gdelt")

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sources SET last_success_at=NOW(), last_error_at=NULL, consecutive_errors=0 WHERE id=%s",
                (source_id,),
            )
        conn.commit()
        log.info("GDELT collected=%s", count)
        return count
    except Exception as exc:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sources SET last_error_at=NOW(), consecutive_errors=consecutive_errors+1 WHERE id=%s",
                (source_id,),
            )
        conn.commit()
        log.exception("GDELT collector failed: %s", exc)
        return 0


def collect_early_signals() -> int:
    conn = psycopg.connect(settings.database_url)
    try:
        total = 0
        try:
            total += collect_gdelt(conn)
        except Exception:
            conn.rollback()
            log.exception("GDELT signal failed")
        try:
            total += collect_google_trends(conn)
        except Exception:
            conn.rollback()
            log.exception("Google Trends signal failed")
        return total
    finally:
        conn.close()
