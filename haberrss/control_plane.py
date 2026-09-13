from __future__ import annotations
import os, time, traceback
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
import psycopg
import redis
from .config import settings

router = APIRouter(prefix="/api/control", tags=["control"])

class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="general", max_length=50)
    weight: float = Field(default=1.0, ge=0, le=10)
    active: bool = True

class SettingsIn(BaseModel):
    scan_interval_seconds: int = Field(default=20, ge=10, le=3600)
    trend_interval_seconds: int = Field(default=5, ge=5, le=3600)
    signal_interval_seconds: int = Field(default=30, ge=30, le=3600)
    source_timeout_seconds: int = Field(default=8, ge=3, le=120)
    max_articles_per_source: int = Field(default=100, ge=10, le=1000)
    publish_mode: str = Field(default="manual", pattern="^(manual|auto)$")
    auto_publish_score: float = Field(default=92, ge=0, le=100)
    alert_score: float = Field(default=75, ge=0, le=100)
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR)$")

def auth(token: str | None):
    if not settings.admin_token or token != settings.admin_token:
        raise HTTPException(401, "unauthorized")

def db(): return psycopg.connect(settings.database_url)

def safe(v):
    return v.isoformat() if hasattr(v, "isoformat") else v

@router.get("/sources")
def list_sources(x_admin_token: str | None = Header(None)):
    auth(x_admin_token)
    with db() as conn, conn.cursor() as c:
        c.execute("SELECT id,name,url,category,active,weight,last_success_at,last_error_at,consecutive_errors FROM sources ORDER BY category,name")
        cols=[d.name for d in c.description]
        return [dict(zip(cols,[safe(x) for x in row])) for row in c.fetchall()]

@router.post("/sources")
def create_source(item: SourceIn, x_admin_token: str | None = Header(None)):
    auth(x_admin_token)
    with db() as conn, conn.cursor() as c:
        try:
            c.execute("INSERT INTO sources(name,url,category,weight,active) VALUES(%s,%s,%s,%s,%s) RETURNING id", (item.name,item.url,item.category,item.weight,item.active))
            source_id=c.fetchone()[0]; conn.commit(); return {"ok":True,"id":source_id}
        except psycopg.errors.UniqueViolation:
            conn.rollback(); raise HTTPException(409,"source URL already exists")

@router.patch("/sources/{source_id}")
def update_source(source_id:int,item:SourceIn,x_admin_token:str|None=Header(None)):
    auth(x_admin_token)
    with db() as conn, conn.cursor() as c:
        c.execute("UPDATE sources SET name=%s,url=%s,category=%s,weight=%s,active=%s WHERE id=%s",(item.name,item.url,item.category,item.weight,item.active,source_id))
        if c.rowcount==0: raise HTTPException(404,"source not found")
        conn.commit(); return {"ok":True}

@router.delete("/sources/{source_id}")
def disable_source(source_id:int,x_admin_token:str|None=Header(None)):
    auth(x_admin_token)
    with db() as conn, conn.cursor() as c:
        c.execute("UPDATE sources SET active=FALSE WHERE id=%s",(source_id,)); conn.commit()
        return {"ok":True,"disabled":c.rowcount>0}

@router.get("/settings")
def get_settings(x_admin_token:str|None=Header(None)):
    auth(x_admin_token)
    return {k:getattr(settings,k) for k in ("scan_interval_seconds","trend_interval_seconds","signal_interval_seconds","source_timeout_seconds","max_articles_per_source","publish_mode","auto_publish_score","alert_score","log_level")}

@router.put("/settings")
def set_settings(item:SettingsIn,x_admin_token:str|None=Header(None)):
    auth(x_admin_token)
    path="/app/.runtime-settings.json"
    data=item.model_dump()
    try:
        import json
        os.makedirs("/app",exist_ok=True)
        tmp=path+".tmp"
        with open(tmp,"w") as f: json.dump(data,f)
        os.replace(tmp,path)
    except Exception as e: raise HTTPException(500,f"settings persistence failed: {e}")
    return {"ok":True,"settings":data,"note":"Runtime workers must reload/restart to apply process-level settings."}

@router.get("/diagnostics")
def diagnostics(x_admin_token:str|None=Header(None)):
    auth(x_admin_token); out={"time":datetime.now(timezone.utc).isoformat(),"checks":{},"errors":[]}
    try:
        with db() as conn, conn.cursor() as c:
            c.execute("SELECT 1"); out["checks"]["postgres"]="ok"
            c.execute("SELECT COUNT(*) FROM articles WHERE discovered_at>=NOW()-INTERVAL '5 minutes'"); out["checks"]["recent_ingest"]=c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM sources WHERE active AND (last_success_at IS NULL OR last_success_at<NOW()-INTERVAL '15 minutes')"); out["checks"]["stale_sources"]=c.fetchone()[0]
    except Exception as e: out["checks"]["postgres"]="error"; out["errors"].append({"component":"postgres","error":str(e)})
    try:
        r=redis.from_url(settings.redis_url); r.ping(); out["checks"]["redis"]="ok"; r.close()
    except Exception as e: out["checks"]["redis"]="error"; out["errors"].append({"component":"redis","error":str(e)})
    return out

@router.get("/errors")
def errors(limit:int=100,x_admin_token:str|None=Header(None)):
    auth(x_admin_token); limit=max(1,min(limit,500))
    with db() as conn, conn.cursor() as c:
        c.execute("SELECT id,name,url,last_error_at,consecutive_errors FROM sources WHERE last_error_at IS NOT NULL ORDER BY last_error_at DESC LIMIT %s",(limit,))
        cols=[d.name for d in c.description]
        return [dict(zip(cols,[safe(x) for x in row])) for row in c.fetchall()]
