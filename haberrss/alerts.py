import logging
import psycopg
import requests
from .config import settings

log = logging.getLogger('haberrss.alerts')


def send_telegram(text: str) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False
    url = f'https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage'
    r = requests.post(url, json={'chat_id': settings.telegram_chat_id, 'text': text, 'disable_web_page_preview': True}, timeout=10)
    r.raise_for_status()
    return True


def alert_breaking() -> int:
    sent = 0
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sc.id, sc.canonical_title, sc.category, sc.article_count,
                       sc.source_count, sc.viral_score, a.url
                FROM story_clusters sc
                LEFT JOIN LATERAL (
                    SELECT url FROM articles WHERE cluster_id=sc.id ORDER BY published_at DESC NULLS LAST LIMIT 1
                ) a ON TRUE
                WHERE sc.viral_score >= %s
                  AND sc.last_seen_at >= NOW() - INTERVAL '30 minutes'
                  AND NOT EXISTS (SELECT 1 FROM posts p WHERE p.cluster_id=sc.id AND p.status IN ('alerted','published'))
                ORDER BY sc.viral_score DESC LIMIT 10
            """, (settings.alert_score,))
            rows = cur.fetchall()
            for cid, title, category, articles, sources, score, url in rows:
                text = f'🚨 GÜNDEM ALARMI\n\n{title}\n\nViral: {score}/100\nKaynak: {sources} | Haber: {articles}\n\n{url or ""}'
                ok = False
                try:
                    ok = send_telegram(text)
                except Exception:
                    log.exception('telegram alert failed')
                if ok:
                    cur.execute("INSERT INTO posts(cluster_id,text,status) VALUES(%s,%s,'alerted')", (cid, text))
                    sent += 1
        conn.commit()
    return sent
