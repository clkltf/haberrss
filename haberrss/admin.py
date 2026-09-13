from __future__ import annotations
import os
import platform
import socket
import time
import psycopg
import redis
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

def db(): return psycopg.connect(settings.database_url)

def check_db():
    try:
        with db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT 1"); c.fetchone()
                c.execute("SELECT COUNT(*) FROM articles WHERE discovered_at >= NOW()-INTERVAL '5 minutes'")
                return True, {"recent_articles": c.fetchone()[0]}
    except Exception as e: return False, {"error": str(e)[:300]}

def check_redis():
    try:
        r=redis.from_url(os.environ.get("REDIS_URL","redis://redis:6379/0"), socket_connect_timeout=2)
        r.ping(); info=r.info("memory"); r.close()
        return True, {"used_memory": info.get("used_memory_human")}
    except Exception as e: return False, {"error": str(e)[:300]}

@router.get("/overview")
def overview(x_admin_token: str | None = Header(default=None)):
    auth(x_admin_token)
    with db() as conn:
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
    with db() as conn:
        with conn.cursor() as c:
            c.execute("SELECT id,canonical_title,category,article_count,source_count,velocity_score,source_score,freshness_score,urgency_score,trend_score,viral_score,state,last_seen_at FROM story_clusters WHERE last_seen_at>=NOW()-INTERVAL '6 hours' ORDER BY viral_score DESC,velocity_score DESC LIMIT %s",(limit,)); return rows(c)

@router.get("/sources")
def sources(x_admin_token:str|None=Header(default=None)):
    auth(x_admin_token)
    with db() as conn:
        with conn.cursor() as c:
            c.execute("SELECT id,name,url,category,active,weight,last_success_at,last_error_at,consecutive_errors FROM sources ORDER BY category,name"); return rows(c)

@router.get("/activity")
def activity(limit:int=100,x_admin_token:str|None=Header(default=None)):
    auth(x_admin_token); limit=max(1,min(limit,500))
    with db() as conn:
        with conn.cursor() as c:
            c.execute("SELECT a.id,a.title,a.url,a.published_at,a.discovered_at,s.name AS source,a.category,COALESCE(sc.viral_score,0) viral_score,COALESCE(sc.state,'new') state FROM articles a LEFT JOIN sources s ON s.id=a.source_id LEFT JOIN story_clusters sc ON sc.id=a.cluster_id ORDER BY a.discovered_at DESC LIMIT %s",(limit,)); return rows(c)

@router.get("/diagnostics")
def diagnostics(x_admin_token:str | None = Header(default=None)):
    auth(x_admin_token)
    started=time.monotonic(); d={"host":socket.gethostname(),"python":platform.python_version(),"platform":platform.platform(),"uptime_check_ms":None}
    ok_db,db_info=check_db(); ok_redis,redis_info=check_redis()
    d.update({"postgres":{"ok":ok_db,**db_info},"redis":{"ok":ok_redis,**redis_info}})
    with db() as conn:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) FROM sources WHERE active AND (last_success_at IS NULL OR last_success_at < NOW()-INTERVAL '15 minutes')"); d["stale_sources"]=c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM story_clusters WHERE last_seen_at >= NOW()-INTERVAL '10 minutes'"); d["active_clusters"]=c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM articles WHERE discovered_at >= NOW()-INTERVAL '5 minutes'"); d["articles_5m"]=c.fetchone()[0]
    d["status"]="healthy" if ok_db and ok_redis else "degraded"
    d["uptime_check_ms"]=round((time.monotonic()-started)*1000,2)
    return d

@router.get("/troubleshooter")
def troubleshooter(x_admin_token: str | None = Header(default=None)):
    auth(x_admin_token); issues=[]
    ok_db,info=check_db(); ok_redis,rinfo=check_redis()
    if not ok_db: issues.append({"severity":"critical","component":"postgres","problem":info.get("error"),"fix":"Kontaineri ve bağlantı değişkenlerini kontrol et."})
    if not ok_redis: issues.append({"severity":"critical","component":"redis","problem":rinfo.get("error"),"fix":"Redis servisini ve REDIS_URL değerini kontrol et."})
    with db() as conn:
        with conn.cursor() as c:
            c.execute("SELECT name,consecutive_errors,last_error_at FROM sources WHERE active AND consecutive_errors>0 ORDER BY consecutive_errors DESC LIMIT 20")
            for name,count,last_error in c.fetchall(): issues.append({"severity":"warning","component":"source","problem":f"{name}: {count} ardışık hata","last_error_at":last_error.isoformat() if last_error else None,"fix":"Kaynak URL'sini ve erişilebilirliğini kontrol et; geçici hataysa otomatik retry beklenir."})
    return {"issue_count":len(issues),"issues":issues,"safe_actions":["Kaynakları yeniden dene","Telegram bağlantısını kontrol et","Redis/DB sağlık kontrolünü yenile"]}

@router.get("/telegram")
def telegram_status(x_admin_token: str | None = Header(default=None)):
    auth(x_admin_token)
    configured=bool(os.environ.get("TELEGRAM_API_ID") and os.environ.get("TELEGRAM_API_HASH") and os.environ.get("TELEGRAM_CHANNELS"))
    channels=[x.strip() for x in os.environ.get("TELEGRAM_CHANNELS","").split(",") if x.strip()]
    with db() as conn:
        with conn.cursor() as c:
            c.execute("SELECT COUNT(*) FROM sources WHERE category='telegram' AND active"); source_count=c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM articles WHERE category='telegram' AND discovered_at>=NOW()-INTERVAL '1 hour'"); articles=c.fetchone()[0]
    return {"configured":configured,"channels":channels,"active_sources":source_count,"articles_1h":articles}
