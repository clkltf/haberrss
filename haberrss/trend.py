import logging
import math
import re
from datetime import datetime, timezone

import psycopg

from .config import settings

log = logging.getLogger("haberrss.trend")

STOP = {
    "bir", "bu", "ve", "ile", "icin", "için", "olan", "olarak", "daha",
    "çok", "son", "gibi", "da", "de", "mi", "mı", "mu", "mü", "ne",
    "nasıl", "kim", "şimdi", "bugün", "yarın", "haber", "haberleri",
    "açıklama", "açıkladı", "etti", "eden", "göre", "karşı", "sonrası",
    "ilgili", "the", "and", "for", "with", "from"
}
URGENT = {
    "son dakika", "acil", "flaş", "şok", "patlama", "deprem", "yangın",
    "öldü", "ölü", "yaralı", "saldırı", "kaza", "tutuklandı", "gözaltı",
    "istifa", "seçim", "zam", "karar", "kriz", "çöktü", "kayboldu", "yasak",
    "saldırıya uğradı", "son dakika gelişmesi", "hayatını kaybetti"
}


def db():
    return psycopg.connect(settings.database_url)


def normalize(text):
    text = (text or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9çğıöşü\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def terms(text):
    return {w for w in normalize(text).split() if len(w) >= 3 and w not in STOP}


def similarity(a, b):
    aa, bb = terms(a), terms(b)
    return len(aa & bb) / len(aa | bb) if aa and bb else 0.0


def urgency(title):
    t = normalize(title)
    return min(100.0, sum(22 for x in URGENT if x in t))


def freshness(age):
    if age <= 3: return 100
    if age <= 5: return 98
    if age <= 10: return 94
    if age <= 20: return 88
    if age <= 30: return 82
    if age <= 60: return 72
    if age <= 180: return 50
    if age <= 360: return 25
    return 10


def bounded_rate(count, minutes):
    # Converts articles/minute into a 0-100 signal without letting one burst dominate forever.
    return min(100.0, (count / max(minutes, 1.0)) * 35.0)


def calculate(count5, count15, count60, sources5, sources15, sources60, age, title, acceleration):
    velocity5 = bounded_rate(count5, 5)
    velocity15 = bounded_rate(count15, 15)
    velocity60 = bounded_rate(count60, 60)
    velocity = min(100.0, velocity5 * 0.55 + velocity15 * 0.30 + velocity60 * 0.15)

    source_velocity = min(100.0, sources5 * 28.0 + sources15 * 6.0 + sources60 * 1.5)
    freshness_score = freshness(age)
    urgency_score = urgency(title)
    volume = min(100.0, math.log(count60 + 1) * 24.0)

    # A story that is spreading across independent sources in minutes gets a large boost.
    trend = (
        velocity * 0.38
        + source_velocity * 0.27
        + acceleration * 0.18
        + freshness_score * 0.10
        + urgency_score * 0.07
    )
    viral = (
        velocity * 0.30
        + source_velocity * 0.24
        + acceleration * 0.22
        + freshness_score * 0.10
        + urgency_score * 0.09
        + volume * 0.05
    )
    return [round(max(0.0, min(100.0, x)), 2) for x in (
        velocity, source_velocity, freshness_score, urgency_score, trend, viral
    )]


def acceleration(conn, cid, count15, sources15):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT article_count, source_count FROM trend_snapshots
               WHERE cluster_id=%s ORDER BY captured_at DESC OFFSET 2 LIMIT 1""",
            (cid,),
        )
        row = cur.fetchone()
    if not row:
        return 0.0
    old_articles, old_sources = row
    article_growth = max(0.0, (count15 - old_articles) / max(old_articles, 1) * 100.0)
    source_growth = max(0.0, (sources15 - old_sources) / max(old_sources, 1) * 100.0)
    return min(100.0, article_growth * 0.65 + source_growth * 0.35)


def run_once():
    conn = db()
    try:
        # Only unclustered recent articles need assignment; older clusters remain stable.
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,title,category,discovered_at FROM articles
                   WHERE cluster_id IS NULL
                     AND discovered_at >= NOW()-INTERVAL '24 hours'
                   ORDER BY discovered_at ASC LIMIT 1000"""
            )
            articles = cur.fetchall()

        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,canonical_title FROM story_clusters
                   WHERE last_seen_at>=NOW()-INTERVAL '24 hours'
                   ORDER BY last_seen_at DESC LIMIT 1500"""
            )
            candidates = cur.fetchall()

        for article_id, title, category, _ in articles:
            best = 0.0
            cluster_id = None
            for cid, canonical in candidates:
                score = similarity(title, canonical)
                if score > best:
                    best, cluster_id = score, cid
            if best < 0.55:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO story_clusters(canonical_title,category) VALUES(%s,%s) RETURNING id",
                        (title, category),
                    )
                    cluster_id = cur.fetchone()[0]
                candidates.append((cluster_id, title))
            with conn.cursor() as cur:
                cur.execute("UPDATE articles SET cluster_id=%s WHERE id=%s", (cluster_id, article_id))
            conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                """SELECT sc.id, sc.canonical_title, sc.category, sc.first_seen_at,
                          COUNT(a.id) FILTER (WHERE a.discovered_at >= NOW()-INTERVAL '5 minutes') AS c5,
                          COUNT(a.id) FILTER (WHERE a.discovered_at >= NOW()-INTERVAL '15 minutes') AS c15,
                          COUNT(a.id) FILTER (WHERE a.discovered_at >= NOW()-INTERVAL '60 minutes') AS c60,
                          COUNT(DISTINCT a.source_id) FILTER (WHERE a.discovered_at >= NOW()-INTERVAL '5 minutes') AS s5,
                          COUNT(DISTINCT a.source_id) FILTER (WHERE a.discovered_at >= NOW()-INTERVAL '15 minutes') AS s15,
                          COUNT(DISTINCT a.source_id) FILTER (WHERE a.discovered_at >= NOW()-INTERVAL '60 minutes') AS s60
                   FROM story_clusters sc
                   JOIN articles a ON a.cluster_id=sc.id
                   WHERE sc.last_seen_at>=NOW()-INTERVAL '24 hours'
                   GROUP BY sc.id, sc.canonical_title, sc.category, sc.first_seen_at"""
            )
            clusters = cur.fetchall()

        now = datetime.now(timezone.utc)
        for cid, title, category, first_seen, c5, c15, c60, s5, s15, s60 in clusters:
            age = max(0.0, (now - first_seen).total_seconds() / 60.0)
            accel = acceleration(conn, cid, c15, s15)
            velocity, src, fresh, urg, trend, viral = calculate(
                c5, c15, c60, s5, s15, s60, age, title, accel
            )
            if viral >= 85:
                state = "breaking"
            elif viral >= 70:
                state = "viral"
            elif viral >= 50:
                state = "trending"
            elif viral >= 30:
                state = "watching"
            else:
                state = "normal"

            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE story_clusters SET last_seen_at=NOW(),article_count=%s,
                       source_count=%s,velocity_score=%s,source_score=%s,
                       freshness_score=%s,urgency_score=%s,trend_score=%s,
                       viral_score=%s,state=%s WHERE id=%s""",
                    (c60, s60, velocity, src, fresh, urg, trend, viral, state, cid),
                )
                cur.execute(
                    """INSERT INTO trend_snapshots(cluster_id,article_count,source_count,trend_score,viral_score)
                       VALUES(%s,%s,%s,%s,%s)""",
                    (cid, c15, s15, trend, viral),
                )
            conn.commit()

        log.info("trend processed clusters=%d", len(clusters))
    finally:
        conn.close()
