import hashlib
import logging
import re
from datetime import datetime, timezone

import psycopg

from .config import settings

log = logging.getLogger("haberrss.trend")

STOP = {
    "bir","bu","ve","ile","icin","için","olan","olarak","daha",
    "çok","çok","son","gibi","da","de","mi","mı","mu","mü",
    "ne","nasıl","kim","şimdi","bugün","yarın","haber","haberleri",
    "açıklama","açıkladı","etti","eden","göre","karşı","sonrası",
    "öncesi","ilgili"
}

URGENT = {
    "son dakika","acil","flaş","şok","patlama","deprem","yangın",
    "öldü","ölü","yaralı","saldırı","kaza","tutuklandı","gözaltı",
    "istifa","seçim","zam","karar","kriz","çöktü","kayboldu"
}


def db():
    return psycopg.connect(settings.database_url)


def normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9çğıöşü\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def terms(text: str) -> set[str]:
    return {w for w in normalize(text).split() if len(w) >= 3 and w not in STOP}


def similarity(a: str, b: str) -> float:
    aa, bb = terms(a), terms(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def urgency(title: str) -> float:
    t = normalize(title)
    return min(100.0, sum(25 for x in URGENT if x in t))


def freshness(age_minutes: float) -> float:
    if age_minutes <= 10: return 100
    if age_minutes <= 30: return 90
    if age_minutes <= 60: return 75
    if age_minutes <= 180: return 55
    if age_minutes <= 360: return 30
    return 10


def source_score(n: int) -> float:
    if n >= 15: return 100
    if n >= 10: return 90
    if n >= 7: return 80
    if n >= 5: return 70
    if n >= 3: return 55
    if n == 2: return 35
    return 15


def calculate(articles: int, sources: int, age_minutes: float, title: str):
    velocity = min(100.0, (articles / max(age_minutes, 1.0)) * 100)
    src = source_score(sources)
    fresh = freshness(age_minutes)
    urg = urgency(title)
    volume = min(100.0, __import__("math").log(articles + 1) * 25)
    trend = velocity * .40 + src * .30 + fresh * .20 + urg * .10
    viral = velocity * .30 + src * .20 + fresh * .15 + urg * .20 + volume * .15
    return [round(x, 2) for x in (velocity, src, fresh, urg, trend, viral)]


def run_once():
    conn = db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, category, discovered_at
                FROM articles
                WHERE cluster_id IS NULL
                  AND discovered_at >= NOW() - INTERVAL '24 hours'
                ORDER BY discovered_at ASC
                LIMIT 500
            """)
            articles = cur.fetchall()

        for article_id, title, category, discovered_at in articles:
            cluster_id = None
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, canonical_title
                    FROM story_clusters
                    WHERE last_seen_at >= NOW() - INTERVAL '24 hours'
                    ORDER BY last_seen_at DESC
                    LIMIT 500
                """)
                candidates = cur.fetchall()

            best = 0.0
            for cid, canonical in candidates:
                s = similarity(title, canonical)
                if s > best:
                    best, cluster_id = s, cid

            if best < 0.55:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO story_clusters (canonical_title, category)
                        VALUES (%s, %s)
                        RETURNING id
                    """, (title, category))
                    cluster_id = cur.fetchone()[0]

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE articles SET cluster_id=%s WHERE id=%s",
                    (cluster_id, article_id),
                )
            conn.commit()

        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    sc.id,
                    sc.canonical_title,
                    sc.category,
                    sc.first_seen_at,
                    COUNT(a.id) AS articles,
                    COUNT(DISTINCT a.source_id) AS sources
                FROM story_clusters sc
                JOIN articles a ON a.cluster_id = sc.id
                WHERE sc.last_seen_at >= NOW() - INTERVAL '24 hours'
                GROUP BY sc.id, sc.canonical_title, sc.category, sc.first_seen_at
            """)
            clusters = cur.fetchall()

        now = datetime.now(timezone.utc)
        for cid, title, category, first_seen, articles, sources in clusters:
            age = (now - first_seen).total_seconds() / 60
            velocity, src, fresh, urg, trend, viral = calculate(
                articles, sources, age, title
            )
            state = "breaking" if viral >= 80 else "trending" if viral >= 60 else "watching" if viral >= 40 else "normal"
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE story_clusters SET
                        last_seen_at=NOW(), article_count=%s, source_count=%s,
                        velocity_score=%s, source_score=%s, freshness_score=%s,
                        urgency_score=%s, trend_score=%s, viral_score=%s, state=%s
                    WHERE id=%s
                """, (articles, sources, velocity, src, fresh, urg, trend, viral, state, cid))
                cur.execute("""
                    INSERT INTO trend_snapshots(cluster_id, article_count, source_count, trend_score, viral_score)
                    VALUES (%s,%s,%s,%s,%s)
                """, (cid, articles, sources, trend, viral))
            conn.commit()
        log.info("trend processed clusters=%d", len(clusters))
    finally:
        conn.close()
