#!/usr/bin/env bash
set -u

APP_DIR="${HABERRSS_DIR:-/opt/haberrss}"
BRANCH="${HABERRSS_BRANCH:-main}"
REPORT_DIR="$APP_DIR/reports"
REPORT="$REPORT_DIR/system-scan.md"
JSON="$REPORT_DIR/system-scan.json"

cd "$APP_DIR" 2>/dev/null || { echo "[FAIL] HaberRSS dizini bulunamadı: $APP_DIR"; exit 1; }
command -v git >/dev/null 2>&1 || { echo "[FAIL] git yok"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "[FAIL] docker yok"; exit 1; }

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "[FAIL] Git repository değil"; exit 1; }

mkdir -p "$REPORT_DIR"
chmod 700 "$REPORT_DIR" 2>/dev/null || true

# Keep credentials and secrets out of the report.
mask(){
  sed -E \
    -e 's/(POSTGRES_PASSWORD=)[^[:space:]]+/\1***MASKED***/g' \
    -e 's/(DATABASE_URL=)[^[:space:]]+/\1***MASKED***/g' \
    -e 's/(REDIS_URL=)[^[:space:]]+/\1***MASKED***/g' \
    -e 's/(TELEGRAM_API_HASH=)[^[:space:]]+/\1***MASKED***/g' \
    -e 's/(TELEGRAM_SESSION=)[^[:space:]]+/\1***MASKED***/g' \
    -e 's/(GEMINI_API_KEY=)[^[:space:]]+/\1***MASKED***/g' \
    -e 's/(X_API_KEY=)[^[:space:]]+/\1***MASKED***/g' \
    -e 's/(X_API_SECRET=)[^[:space:]]+/\1***MASKED***/g' \
    -e 's/(X_ACCESS_TOKEN=)[^[:space:]]+/\1***MASKED***/g' \
    -e 's/(X_ACCESS_TOKEN_SECRET=)[^[:space:]]+/\1***MASKED***/g'
}

q(){ docker compose exec -T postgres psql -U "${POSTGRES_USER:-haberrss}" -d "${POSTGRES_DB:-haberrss}" -Atc "$1" 2>/dev/null; }

NEWS=$(q 'SELECT COUNT(*) FROM news;' | tr -d '[:space:]'); NEWS=${NEWS:-0}
SOURCES=$(q 'SELECT COUNT(*) FROM sources;' | tr -d '[:space:]'); SOURCES=${SOURCES:-0}
CLUSTERS=$(q 'SELECT COUNT(*) FROM story_clusters;' | tr -d '[:space:]'); CLUSTERS=${CLUSTERS:-0}
CLUSTER_ARTICLES=$(q 'SELECT COUNT(*) FROM cluster_articles;' | tr -d '[:space:]'); CLUSTER_ARTICLES=${CLUSTER_ARTICLES:-0}
TRENDS=$(q 'SELECT COUNT(*) FROM trends;' | tr -d '[:space:]'); TRENDS=${TRENDS:-0}
NEWS_1H=$(q "SELECT COUNT(*) FROM news WHERE published_at >= NOW() - INTERVAL '1 hour';" | tr -d '[:space:]'); NEWS_1H=${NEWS_1H:-0}
NEWS_24H=$(q "SELECT COUNT(*) FROM news WHERE published_at >= NOW() - INTERVAL '24 hours';" | tr -d '[:space:]'); NEWS_24H=${NEWS_24H:-0}

APP_STATUS=$(docker compose ps --status running app 2>/dev/null | grep -q app && echo running || echo not-running)
APP_HEALTH=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$(docker compose ps -q app 2>/dev/null)" 2>/dev/null || echo unknown)
PG_OK=$(docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-haberrss}" -d "${POSTGRES_DB:-haberrss}" >/dev/null 2>&1 && echo true || echo false)
REDIS_OK=$(docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG && echo true || echo false)
GDELT_ERRORS=$(docker compose logs --tail=500 app 2>/dev/null | grep -c 'GDELT collector failed' || true)
APP_ERRORS=$(docker compose logs --tail=500 app 2>/dev/null | grep -Ec 'ERROR|Traceback|CRITICAL' || true)
RESTARTING=$(docker compose ps 2>/dev/null | grep -c 'Restarting' || true)

if [ "$NEWS" -gt 0 ] && [ "$CLUSTERS" -eq 0 ]; then CLUSTER_P0=true; else CLUSTER_P0=false; fi
if [ "$GDELT_ERRORS" -gt 0 ]; then GDELT_FAIL=true; else GDELT_FAIL=false; fi

GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
HOST=$(hostname 2>/dev/null || echo unknown)
DATE=$(date -Is)

cat > "$REPORT" <<EOF
# HaberRSS Otomatik Sistem Taraması

- **Tarih:** $DATE
- **Sunucu:** $HOST
- **Git commit:** $GIT_COMMIT
- **Branch:** $BRANCH

## Özet

| Kontrol | Sonuç |
|---|---:|
| App | $APP_STATUS |
| App health | $APP_HEALTH |
| PostgreSQL | $PG_OK |
| Redis | $REDIS_OK |
| News | $NEWS |
| Sources | $SOURCES |
| Story clusters | $CLUSTERS |
| Cluster articles | $CLUSTER_ARTICLES |
| Trends | $TRENDS |
| News son 1 saat | $NEWS_1H |
| News son 24 saat | $NEWS_24H |
| GDELT hata sayısı (son 500 log) | $GDELT_ERRORS |
| App hata sayısı (son 500 log) | $APP_ERRORS |
| Restarting servis sayısı | $RESTARTING |
| Cluster P0 | $CLUSTER_P0 |

## P0 / Kritik

EOF

if [ "$CLUSTER_P0" = true ]; then echo "- **P0:** $NEWS haber var ancak story_clusters = 0. Cluster motoru çalışmıyor veya cluster üretmiyor." >> "$REPORT"; fi
if [ "$GDELT_FAIL" = true ]; then echo "- **P1:** GDELT son loglarda $GDELT_ERRORS hata üretti." >> "$REPORT"; fi
if [ "$RESTARTING" -gt 0 ]; then echo "- **P1:** En az bir servis restart döngüsünde." >> "$REPORT"; fi
if [ "$APP_STATUS" != running ]; then echo "- **P0:** App çalışmıyor." >> "$REPORT"; fi
if [ "$PG_OK" != true ]; then echo "- **P0:** PostgreSQL bağlantısı başarısız." >> "$REPORT"; fi
if [ "$REDIS_OK" != true ]; then echo "- **P0:** Redis bağlantısı başarısız." >> "$REPORT"; fi
if [ "$CLUSTER_P0" = false ] && [ "$GDELT_FAIL" = false ] && [ "$RESTARTING" -eq 0 ] && [ "$APP_STATUS" = running ] && [ "$PG_OK" = true ] && [ "$REDIS_OK" = true ]; then echo "- Kritik otomatik bulgu yok." >> "$REPORT"; fi

cat >> "$REPORT" <<EOF

## Container Durumu

\`\`\`text
$(docker compose ps 2>&1 | mask)
\`\`\`

## Son Collector Kayıtları

\`\`\`text
$(docker compose logs --tail=80 app 2>&1 | grep -E 'collector source=|entries=|worker starting|trend|GDELT|ERROR|WARNING' | tail -80 | mask)
\`\`\`

## Son Hatalar

\`\`\`text
$(docker compose logs --tail=300 app 2>&1 | grep -E 'ERROR|Traceback|CRITICAL|GDELT' | tail -80 | mask)
\`\`\`

## Veritabanı Kontrolleri

\`\`\`text
$(q "SELECT 'news_by_source'; SELECT source, COUNT(*) FROM news GROUP BY source ORDER BY COUNT(*) DESC LIMIT 20;" | mask)
\`\`\`

## Kaynaklar

\`\`\`text
$(q 'SELECT id, name, url, category FROM sources ORDER BY id;' | mask)
\`\`\`

## Son Haberler

\`\`\`text
$(q "SELECT id, LEFT(title,180), source, published_at FROM news ORDER BY published_at DESC LIMIT 20;" | mask)
\`\`\`

## Git Durumu

\`\`\`text
$(git status --short 2>&1 | head -80 | mask)
\`\`\`
EOF

# Machine-readable summary for later automated analysis.
cat > "$JSON" <<EOF
{
  "timestamp": "$(date -Is)",
  "host": "$(printf '%s' "$HOST" | sed 's/"/\\"/g')",
  "git_commit": "$GIT_COMMIT",
  "app_status": "$APP_STATUS",
  "app_health": "$APP_HEALTH",
  "postgres_ok": $PG_OK,
  "redis_ok": $REDIS_OK,
  "news": $NEWS,
  "sources": $SOURCES,
  "story_clusters": $CLUSTERS,
  "cluster_articles": $CLUSTER_ARTICLES,
  "trends": $TRENDS,
  "news_1h": $NEWS_1H,
  "news_24h": $NEWS_24H,
  "gdelt_errors_last_500": $GDELT_ERRORS,
  "app_errors_last_500": $APP_ERRORS,
  "restarting_services": $RESTARTING,
  "cluster_p0": $CLUSTER_P0,
  "gdelt_fail": $GDELT_FAIL
}
EOF

chmod 644 "$REPORT" "$JSON"

git add "$REPORT" "$JSON"
if git diff --cached --quiet; then
  echo "[INFO] Yeni rapor değişikliği yok. GitHub'a push gerekmiyor."
  exit 0
fi

git commit -m "chore: update automatic system scan" >/tmp/haberrss-scan-commit.log 2>&1 || {
  cat /tmp/haberrss-scan-commit.log
  echo "[FAIL] Git commit başarısız"
  exit 1
}

git push origin "$BRANCH" >/tmp/haberrss-scan-push.log 2>&1 || {
  cat /tmp/haberrss-scan-push.log
  echo "[FAIL] GitHub push başarısız. Sunucunun GitHub kimlik doğrulamasını kontrol et."
  exit 2
}

cat /tmp/haberrss-scan-commit.log
cat /tmp/haberrss-scan-push.log
echo
echo "[OK] Tarama GitHub'a aktarıldı: reports/system-scan.md"
echo "[OK] Makine raporu: reports/system-scan.json"
