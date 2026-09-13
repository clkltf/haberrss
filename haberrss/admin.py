from __future__ import annotations
import os, platform, socket, time
import psycopg, redis
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from .config import settings
from .runtime import load as runtime_load, save as runtime_save

router=APIRouter(prefix='/api/admin',tags=['admin'])
def auth(t):
    if not settings.admin_token: raise HTTPException(503,'ADMIN_TOKEN is not configured')
    if t!=settings.admin_token: raise HTTPException(401,'unauthorized')
def db(): return psycopg.connect(settings.database_url)
def rows(c): return [dict(zip([d.name for d in c.description],r)) for r in c.fetchall()]

def db_check():
    try:
      with db() as x:
       with x.cursor() as c:c.execute('SELECT 1'); c.fetchone(); return True,{}
    except Exception as e:return False,{'error':str(e)[:500]}
def redis_check():
    try:
      r=redis.from_url(settings.redis_url,socket_connect_timeout=2);r.ping();i=r.info('memory');r.close();return True,{'used_memory':i.get('used_memory_human')}
    except Exception as e:return False,{'error':str(e)[:500]}

class SourceIn(BaseModel):
 name:str=Field(min_length=1,max_length=200); url:str=Field(min_length=5,max_length=2000); category:str=Field(default='general',max_length=80); weight:float=Field(default=1,ge=0,le=10); active:bool=True
class SettingsIn(BaseModel):
 scan_interval_seconds:int=Field(default=20,ge=5,le=3600); trend_interval_seconds:int=Field(default=5,ge=5,le=3600); signal_interval_seconds:int=Field(default=30,ge=10,le=3600); source_timeout_seconds:int=Field(default=8,ge=3,le=120); max_articles_per_source:int=Field(default=100,ge=10,le=1000); publish_mode:str=Field(default='manual',pattern='^(manual|auto)$'); auto_publish_score:float=Field(default=92,ge=0,le=100); alert_score:float=Field(default=75,ge=0,le=100); log_level:str=Field(default='INFO',pattern='^(DEBUG|INFO|WARNING|ERROR)$')

@router.get('/overview')
def overview(x_admin_token:str|None=Header(None)):
 auth(x_admin_token)
 with db() as x:
  with x.cursor() as c:
   def q(sql): c.execute(sql);return c.fetchone()[0]
   return {'articles_24h':q("SELECT COUNT(*) FROM articles WHERE discovered_at>=NOW()-INTERVAL '24 hours'"),'active_sources':q('SELECT COUNT(*) FROM sources WHERE active'),'clusters_24h':q("SELECT COUNT(*) FROM story_clusters WHERE last_seen_at>=NOW()-INTERVAL '24 hours'"),'breaking':q("SELECT COUNT(*) FROM story_clusters WHERE viral_score>=75 AND last_seen_at>=NOW()-INTERVAL '30 minutes'"),'posts_24h':q("SELECT COUNT(*) FROM posts WHERE status='published' AND published_at>=NOW()-INTERVAL '24 hours'"),'stale_sources':q("SELECT COUNT(*) FROM sources WHERE active AND (last_success_at IS NULL OR last_success_at<NOW()-INTERVAL '15 minutes')")}

@router.get('/breaking')
def breaking(limit:int=30,x_admin_token:str|None=Header(None)):
 auth(x_admin_token);limit=max(1,min(limit,100))
 with db() as x:
  with x.cursor() as c:c.execute("SELECT id,canonical_title,category,article_count,source_count,velocity_score,source_score,freshness_score,urgency_score,trend_score,viral_score,state,last_seen_at FROM story_clusters WHERE last_seen_at>=NOW()-INTERVAL '6 hours' ORDER BY viral_score DESC,velocity_score DESC LIMIT %s",(limit,));return rows(c)

@router.get('/sources')
def sources(x_admin_token:str|None=Header(None)):
 auth(x_admin_token)
 with db() as x:
  with x.cursor() as c:c.execute("SELECT id,name,url,category,active,weight,last_success_at,last_error_at,consecutive_errors FROM sources ORDER BY active DESC,category,name");return rows(c)
@router.post('/sources')
def add_source(s:SourceIn,x_admin_token:str|None=Header(None)):
 auth(x_admin_token)
 try:
  with db() as x:
   with x.cursor() as c:c.execute('INSERT INTO sources(name,url,category,active,weight) VALUES(%s,%s,%s,%s,%s) RETURNING id',(s.name,s.url,s.category,s.active,s.weight));i=c.fetchone()[0];x.commit();return {'ok':True,'id':i}
 except psycopg.errors.UniqueViolation: raise HTTPException(409,'source already exists')
@router.put('/sources/{source_id}')
def update_source(source_id:int,s:SourceIn,x_admin_token:str|None=Header(None)):
 auth(x_admin_token)
 with db() as x:
  with x.cursor() as c:c.execute('UPDATE sources SET name=%s,url=%s,category=%s,active=%s,weight=%s WHERE id=%s',(s.name,s.url,s.category,s.active,s.weight,source_id));n=c.rowcount;x.commit();return {'ok':n==1}
@router.patch('/sources/{source_id}/active')
def toggle_source(source_id:int,active:bool,x_admin_token:str|None=Header(None)):
 auth(x_admin_token)
 with db() as x:
  with x.cursor() as c:c.execute('UPDATE sources SET active=%s WHERE id=%s',(active,source_id));n=c.rowcount;x.commit();return {'ok':n==1,'active':active}
@router.delete('/sources/{source_id}')
def delete_source(source_id:int,x_admin_token:str|None=Header(None)):
 auth(x_admin_token)
 with db() as x:
  with x.cursor() as c:c.execute('UPDATE sources SET active=FALSE WHERE id=%s',(source_id,));n=c.rowcount;x.commit();return {'ok':n==1,'disabled':True}
@router.post('/sources/{source_id}/test')
def test_source(source_id:int,x_admin_token:str|None=Header(None)):
 auth(x_admin_token)
 with db() as x:
  with x.cursor() as c:c.execute('SELECT id,name,url,active FROM sources WHERE id=%s',(source_id,));r=c.fetchone()
 if not r: raise HTTPException(404,'source not found')
 import urllib.request
 try:
  req=urllib.request.Request(r[2],headers={'User-Agent':'HaberRSS/1.0'})
  with urllib.request.urlopen(req,timeout=10) as resp:return {'ok':True,'status':resp.status,'content_type':resp.headers.get('content-type'),'source':r[1]}
 except Exception as e:return {'ok':False,'source':r[1],'error':str(e)[:500]}

@router.get('/settings')
def get_settings(x_admin_token:str|None=Header(None)):auth(x_admin_token);return runtime_load()
@router.put('/settings')
def put_settings(s:SettingsIn,x_admin_token:str|None=Header(None)):
 auth(x_admin_token);return {'ok':True,'live':True,'settings':runtime_save(s.model_dump())}

@router.get('/diagnostics')
def diagnostics(x_admin_token:str|None=Header(None)):
 auth(x_admin_token);t=time.monotonic();okdb,di=db_check();okr,ri=redis_check();d={'host':socket.gethostname(),'python':platform.python_version(),'postgres':{'ok':okdb,**di},'redis':{'ok':okr,**ri}}
 with db() as x:
  with x.cursor() as c:
   for k,sql in {'stale_sources':"SELECT COUNT(*) FROM sources WHERE active AND (last_success_at IS NULL OR last_success_at<NOW()-INTERVAL '15 minutes')",'active_clusters':"SELECT COUNT(*) FROM story_clusters WHERE last_seen_at>=NOW()-INTERVAL '10 minutes'",'articles_5m':"SELECT COUNT(*) FROM articles WHERE discovered_at>=NOW()-INTERVAL '5 minutes'"}.items():c.execute(sql);d[k]=c.fetchone()[0]
 d['runtime']=runtime_load();d['status']='healthy' if okdb and okr else 'degraded';d['latency_ms']=round((time.monotonic()-t)*1000,2);return d

@router.get('/troubleshooter')
def troubleshooter(x_admin_token:str|None=Header(None)):
 auth(x_admin_token);issues=[];okdb,di=db_check();okr,ri=redis_check()
 if not okdb:issues.append({'severity':'critical','component':'postgres','problem':di.get('error'),'fix':'PostgreSQL bağlantısını ve DATABASE_URL değerini kontrol et.'})
 if not okr:issues.append({'severity':'critical','component':'redis','problem':ri.get('error'),'fix':'Redis servisini ve REDIS_URL değerini kontrol et.'})
 with db() as x:
  with x.cursor() as c:
   c.execute("SELECT name,consecutive_errors,last_error_at FROM sources WHERE active AND consecutive_errors>0 ORDER BY consecutive_errors DESC LIMIT 50")
   for name,count,last_error in c.fetchall():issues.append({'severity':'warning','component':'source','problem':f'{name}: {count} ardışık hata','last_error_at':last_error.isoformat() if last_error else None,'fix':'Kaynağı test et; başarısızsa pasifleştir veya URLyi düzelt.'})
 return {'issue_count':len(issues),'issues':issues}

@router.get('/activity')
def activity(limit:int=100,x_admin_token:str|None=Header(None)):
 auth(x_admin_token);limit=max(1,min(limit,500))
 with db() as x:
  with x.cursor() as c:c.execute("SELECT a.id,a.title,a.url,a.published_at,a.discovered_at,s.name AS source,a.category,COALESCE(sc.viral_score,0) viral_score,COALESCE(sc.state,'new') state FROM articles a LEFT JOIN sources s ON s.id=a.source_id LEFT JOIN story_clusters sc ON sc.id=a.cluster_id ORDER BY a.discovered_at DESC LIMIT %s",(limit,));return rows(c)

@router.get('/telegram')
def telegram_status(x_admin_token:str|None=Header(None)):
 auth(x_admin_token);channels=[x.strip() for x in os.environ.get('TELEGRAM_CHANNELS','').split(',') if x.strip()];configured=bool(os.environ.get('TELEGRAM_API_ID') and os.environ.get('TELEGRAM_API_HASH') and channels)
 with db() as x:
  with x.cursor() as c:c.execute("SELECT COUNT(*) FROM sources WHERE category='telegram' AND active");sc=c.fetchone()[0];c.execute("SELECT COUNT(*) FROM articles WHERE category='telegram' AND discovered_at>=NOW()-INTERVAL '1 hour'");a=c.fetchone()[0]
 return {'configured':configured,'channels':channels,'active_sources':sc,'articles_1h':a}
