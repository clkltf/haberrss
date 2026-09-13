import logging
import math
import re
from datetime import datetime, timezone
import psycopg
from .config import settings
log = logging.getLogger("haberrss.trend")
STOP={"bir","bu","ve","ile","icin","için","olan","olarak","daha","çok","son","gibi","da","de","mi","mı","mu","mü","ne","nasıl","kim","şimdi","bugün","yarın","haber","haberleri","açıklama","açıkladı","etti","eden","göre","karşı","sonrası","ilgili"}
URGENT={"son dakika","acil","flaş","şok","patlama","deprem","yangın","öldü","ölü","yaralı","saldırı","kaza","tutuklandı","gözaltı","istifa","seçim","zam","karar","kriz","çöktü","kayboldu","yasak","saldırıya uğradı"}

def db(): return psycopg.connect(settings.database_url)
def normalize(text):
    text=(text or "").lower(); text=re.sub(r"https?://\S+"," ",text); text=re.sub(r"[^a-z0-9çğıöşü\s]"," ",text); return re.sub(r"\s+"," ",text).strip()
def terms(text): return {w for w in normalize(text).split() if len(w)>=3 and w not in STOP}
def similarity(a,b):
    aa,bb=terms(a),terms(b)
    return len(aa&bb)/len(aa|bb) if aa and bb else 0.0
def urgency(title):
    t=normalize(title); return min(100.0,sum(25 for x in URGENT if x in t))
def freshness(age):
    if age<=5:return 100
    if age<=10:return 96
    if age<=20:return 92
    if age<=30:return 86
    if age<=60:return 75
    if age<=180:return 55
    if age<=360:return 30
    return 10
def source_score(n):
    if n>=15:return 100
    if n>=10:return 92
    if n>=7:return 82
    if n>=5:return 72
    if n>=3:return 56
    if n==2:return 38
    return 15

def acceleration(conn,cid,articles):
    with conn.cursor() as cur:
        cur.execute("SELECT article_count FROM trend_snapshots WHERE cluster_id=%s ORDER BY captured_at DESC OFFSET 2 LIMIT 1",(cid,))
        row=cur.fetchone()
    if not row:return 0.0
    old=max(0,row[0]); return min(100.0,max(0.0,(articles-old)/max(old,1)*100))

def calculate(articles,sources,age,title,accel):
    # Velocity is bounded; acceleration rewards stories that are suddenly taking off.
    velocity=min(100.0,(articles/max(age,1.0))*100)
    src=source_score(sources); fresh=freshness(age); urg=urgency(title)
    volume=min(100.0,math.log(articles+1)*25)
    trend=velocity*.32+accel*.18+src*.25+fresh*.15+urg*.10
    viral=velocity*.24+accel*.20+src*.18+fresh*.13+urg*.15+volume*.10
    return [round(x,2) for x in (velocity,src,fresh,urg,trend,viral)]

def run_once():
    conn=db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id,title,category,discovered_at FROM articles WHERE cluster_id IS NULL AND discovered_at>=NOW()-INTERVAL '24 hours' ORDER BY discovered_at ASC LIMIT 500")
            articles=cur.fetchall()
        for article_id,title,category,_ in articles:
            with conn.cursor() as cur:
                cur.execute("SELECT id,canonical_title FROM story_clusters WHERE last_seen_at>=NOW()-INTERVAL '24 hours' ORDER BY last_seen_at DESC LIMIT 1000")
                candidates=cur.fetchall()
            best=0.0; cluster_id=None
            for cid,canonical in candidates:
                s=similarity(title,canonical)
                if s>best: best,cluster_id=s,cid
            if best<0.55:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO story_clusters(canonical_title,category) VALUES(%s,%s) RETURNING id",(title,category)); cluster_id=cur.fetchone()[0]
            with conn.cursor() as cur: cur.execute("UPDATE articles SET cluster_id=%s WHERE id=%s",(cluster_id,article_id))
            conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT sc.id,sc.canonical_title,sc.category,sc.first_seen_at,COUNT(a.id),COUNT(DISTINCT a.source_id) FROM story_clusters sc JOIN articles a ON a.cluster_id=sc.id WHERE sc.last_seen_at>=NOW()-INTERVAL '24 hours' GROUP BY sc.id,sc.canonical_title,sc.category,sc.first_seen_at")
            clusters=cur.fetchall()
        now=datetime.now(timezone.utc)
        for cid,title,category,first_seen,articles_count,sources in clusters:
            age=max(0,(now-first_seen).total_seconds()/60); accel=acceleration(conn,cid,articles_count)
            velocity,src,fresh,urg,trend,viral=calculate(articles_count,sources,age,title,accel)
            state="breaking" if viral>=80 else "trending" if viral>=60 else "watching" if viral>=40 else "normal"
            with conn.cursor() as cur:
                cur.execute("UPDATE story_clusters SET last_seen_at=NOW(),article_count=%s,source_count=%s,velocity_score=%s,source_score=%s,freshness_score=%s,urgency_score=%s,trend_score=%s,viral_score=%s,state=%s WHERE id=%s",(articles_count,sources,velocity,src,fresh,urg,trend,viral,state,cid))
                cur.execute("INSERT INTO trend_snapshots(cluster_id,article_count,source_count,trend_score,viral_score) VALUES(%s,%s,%s,%s,%s)",(cid,articles_count,sources,trend,viral))
            conn.commit()
        log.info("trend processed clusters=%d",len(clusters))
    finally: conn.close()
