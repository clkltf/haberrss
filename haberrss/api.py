from fastapi import FastAPI
from fastapi.responses import JSONResponse
import psycopg

from .config import settings

app = FastAPI(title="HaberRSS", version="0.1.0")

@app.get("/health")
def health():
    db_ok = False
    try:
        with psycopg.connect(settings.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                db_ok = cur.fetchone() == (1,)
    except Exception:
        db_ok = False
    return JSONResponse({"status": "ok" if db_ok else "degraded", "postgres": db_ok})

@app.get("/api/top-trends")
def top_trends(limit: int = 20):
    limit = max(1, min(limit, 100))
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, canonical_title, category, article_count,
                       source_count, trend_score, viral_score, state,
                       last_seen_at
                FROM story_clusters
                WHERE last_seen_at >= NOW() - INTERVAL '24 hours'
                ORDER BY viral_score DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "title": r[1],
            "category": r[2],
            "articles": r[3],
            "sources": r[4],
            "trend_score": float(r[5]),
            "viral_score": float(r[6]),
            "state": r[7],
            "last_seen_at": r[8].isoformat(),
        }
        for r in rows
    ]
