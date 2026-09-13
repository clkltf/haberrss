import hashlib
import logging
import re
from datetime import datetime, timezone

import feedparser
import psycopg
from bs4 import BeautifulSoup

from .config import settings
from .sources import SOURCES

log = logging.getLogger("haberrss.collector")


def clean(text: str) -> str:
    text = BeautifulSoup(text or "", "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", text).strip()


def title_hash(title: str) -> str:
    normalized = re.sub(r"[^a-z0-9çğıöşü ]", "", title.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def connect():
    return psycopg.connect(settings.database_url)


def ensure_sources(conn) -> None:
    with conn.cursor() as cur:
        for name, url, category in SOURCES:
            cur.execute(
                """
                INSERT INTO sources (name, url, category)
                VALUES (%s, %s, %s)
                ON CONFLICT (url) DO UPDATE
                SET name = EXCLUDED.name,
                    category = EXCLUDED.category,
                    active = TRUE
                """,
                (name, url, category),
            )
    conn.commit()


def parse_published(entry):
    parsed = getattr(entry, "published_parsed", None)
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def collect_once() -> int:
    conn = connect()
    ensure_sources(conn)
    inserted = 0

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, url, category FROM sources WHERE active = TRUE")
            source_rows = cur.fetchall()

        for source_id, name, url, category in source_rows:
            try:
                feed = feedparser.parse(url)
                entries = getattr(feed, "entries", [])[:100]

                with conn.cursor() as cur:
                    for entry in entries:
                        title = clean(getattr(entry, "title", ""))
                        link = getattr(entry, "link", "").strip()
                        summary = clean(getattr(entry, "summary", ""))
                        if not title or not link:
                            continue

                        cur.execute(
                            """
                            INSERT INTO articles (
                                source_id, title, url, summary,
                                published_at, title_hash, category
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (url) DO NOTHING
                            """,
                            (
                                source_id,
                                title,
                                link,
                                summary,
                                parse_published(entry),
                                title_hash(title),
                                category,
                            ),
                        )
                        inserted += cur.rowcount

                    cur.execute(
                        """
                        UPDATE sources
                        SET last_success_at = NOW(),
                            consecutive_errors = 0
                        WHERE id = %s
                        """,
                        (source_id,),
                    )

                conn.commit()
                log.info("source=%s entries=%d", name, len(entries))

            except Exception as exc:
                conn.rollback()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE sources
                        SET last_error_at = NOW(),
                            consecutive_errors = consecutive_errors + 1
                        WHERE id = %s
                        """,
                        (source_id,),
                    )
                conn.commit()
                log.warning("source=%s error=%s", name, exc)

        return inserted
    finally:
        conn.close()
