from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
import psycopg
from .config import settings
from .admin import router as admin_router

app = FastAPI(title="HaberRSS Control Plane", version="1.0.0")
app.include_router(admin_router)

@app.get("/health")
def health():
    checks = {"postgres": False, "recent_ingest": False}
    try:
        with psycopg.connect(settings.database_url) as conn:
            with conn.cursor() as c:
                c.execute("SELECT 1")
                checks["postgres"] = c.fetchone() == (1,)
                c.execute("SELECT EXISTS(SELECT 1 FROM articles WHERE discovered_at >= NOW()-INTERVAL '10 minutes')")
                checks["recent_ingest"] = c.fetchone()[0]
    except Exception:
        pass
    ok = all(checks.values())
    return JSONResponse({"status": "ok" if ok else "degraded", "checks": checks})

@app.get("/api/top-trends")
def top_trends(limit: int = 20):
    limit = max(1, min(limit, 100))
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, canonical_title, category, article_count, source_count,
                       velocity_score, source_score, freshness_score, urgency_score,
                       trend_score, viral_score, state, first_seen_at, last_seen_at
                FROM story_clusters
                WHERE last_seen_at >= NOW() - INTERVAL '24 hours'
                ORDER BY viral_score DESC, last_seen_at DESC LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
    keys = ["id","title","category","articles","sources","velocity","source_score","freshness","urgency","trend_score","viral_score","state","first_seen_at","last_seen_at"]
    return [dict(zip(keys, [float(x) if isinstance(x, (int,float)) and i >= 5 and i <= 10 else x.isoformat() if hasattr(x,'isoformat') else x for i,x in enumerate(r)])) for r in rows]
