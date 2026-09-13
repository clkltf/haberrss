import psycopg
from fastapi import APIRouter, Header, HTTPException
from .config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])

def auth(x_admin_token: str | None):
    expected = settings.admin_token
    if not expected:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN is not configured")
    if x_admin_token != expected:
        raise HTTPException(status_code=401, detail="unauthorized")

def rows(cur):
    return [dict(zip([d.name for d in cur.description], r)) for r in cur.fetchall()]

@router.get("/overview")
def overview(x_admin_token: str | None = Header(default=None)):
    auth(x_admin_token)
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) FROM articles WHERE discovered_at >= NOW()-INTERVAL '24 hours'"); articles=c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM sources WHERE active"); sources=c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM story_clusters WHERE last_seen_at >= NOW()-INTERVAL '24 hours'"); clusters=c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM story_clusters WHERE viral_score >= 75 AND last_seen_at >= NOW()-INTERVAL '30 minutes'"); breaking=c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM posts WHERE status='published' AND published_at >= NOW()-INTERVAL '24 hours'"); posts=c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM sources WHERE active AND (last_success_at IS NULL OR last_success_at < NOW()-INTERVAL '15 minutes')"); stale=c.fetchone()[0]
    return {'articles_24h':articles,'active_sources':sources,'clusters_24h':clusters,'breaking':breaking,'posts_24h':posts,'stale_sources':stale}

@router.get("/breaking")
def breaking(limit:int=30,x_admin_token:str|None=Header(default=None)):
    auth(x_admin_token); limit=max(1,min(limit,100))
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as c:
            c.execute("SELECT id,canonical_title,category,article_count,source_count,velocity_score,source_score,freshness_score,urgency_score,trend_score,viral_score,state,last_seen_at FROM story_clusters WHERE last_seen_at>=NOW()-INTERVAL '6 hours' ORDER BY viral_score DESC,velocity_score DESC LIMIT %s",(limit,)); return rows(c)

@router.get("/sources")
def sources(x_admin_token:str|None=Header(default=None)):
    auth(x_admin_token)
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as c:
            c.execute("SELECT id,name,url,category,active,weight,last_success_at,last_error_at,consecutive_errors FROM sources ORDER BY category,name"); return rows(c)

@router.get("/activity")
def activity(limit:int=100,x_admin_token:str|None=Header(default=None)):
    auth(x_admin_token); limit=max(1,min(limit,500))
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as c:
            c.execute("SELECT a.id,a.title,a.url,a.published_at,a.discovered_at,s.name AS source,a.category,COALESCE(sc.viral_score,0) viral_score,COALESCE(sc.state,'new') state FROM articles a LEFT JOIN sources s ON s.id=a.source_id LEFT JOIN story_clusters sc ON sc.id=a.cluster_id ORDER BY a.discovered_at DESC LIMIT %s",(limit,)); return rows(c)
