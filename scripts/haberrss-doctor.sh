#!/usr/bin/env bash
set -u

APP_DIR="${HABERRSS_DIR:-/opt/haberrss}"
cd "$APP_DIR" 2>/dev/null || { echo "[FAIL] HaberRSS dizini bulunamadı: $APP_DIR"; exit 1; }

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
PASS=0; WARN=0; FAIL=0

ok(){ echo -e "${GREEN}[ OK ]${NC} $*"; PASS=$((PASS+1)); }
warn(){ echo -e "${YELLOW}[WARN]${NC} $*"; WARN=$((WARN+1)); }
bad(){ echo -e "${RED}[FAIL]${NC} $*"; FAIL=$((FAIL+1)); }
head(){ echo; echo -e "${BLUE}===== $* =====${NC}"; }

head "HABERRSS SYSTEM DOCTOR"
echo "Tarih: $(date -Is)"
echo "Dizin: $APP_DIR"

head "HOST"
command -v docker >/dev/null 2>&1 && ok "Docker: $(docker --version)" || bad "Docker yok"
command -v git >/dev/null 2>&1 && ok "Git hazır" || bad "Git yok"
free -h | sed -n '1,2p' || true
df -h "$APP_DIR" | tail -1 || true

head "GIT"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ok "Git repository"
  echo "Branch: $(git branch --show-current 2>/dev/null || true)"
  echo "Commit: $(git rev-parse --short HEAD 2>/dev/null || true)"
  if git diff --quiet 2>/dev/null; then ok "Çalışma ağacı temiz"; else warn "Sunucuda commit edilmemiş değişiklik var"; fi
else
  bad "Git repository değil"
fi

head "COMPOSE / CONTAINERS"
if docker compose config >/dev/null 2>&1; then ok "docker compose config geçerli"; else bad "docker compose config hatalı"; fi
docker compose ps 2>/dev/null || true

for svc in postgres redis app; do
  if docker compose ps --status running "$svc" 2>/dev/null | grep -q "$svc"; then ok "$svc çalışıyor"; else bad "$svc çalışmıyor"; fi
done

head "POSTGRES"
if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-haberrss}" -d "${POSTGRES_DB:-haberrss}" >/dev/null 2>&1; then
  ok "PostgreSQL bağlantısı"
  docker compose exec -T postgres psql -U "${POSTGRES_USER:-haberrss}" -d "${POSTGRES_DB:-haberrss}" -Atc "SELECT 'news='||COUNT(*) FROM news; SELECT 'sources='||COUNT(*) FROM sources; SELECT 'story_clusters='||COUNT(*) FROM story_clusters; SELECT 'cluster_articles='||COUNT(*) FROM cluster_articles; SELECT 'trends='||COUNT(*) FROM trends;" 2>/dev/null || warn "Tablo sorgusu başarısız"
else
  bad "PostgreSQL hazır değil"
fi

head "REDIS"
if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then ok "Redis PONG"; else bad "Redis cevap vermiyor"; fi

head "APP HEALTH"
APP_CID=$(docker compose ps -q app 2>/dev/null || true)
if [ -n "$APP_CID" ]; then
  STATUS=$(docker inspect -f '{{.State.Status}}' "$APP_CID" 2>/dev/null || echo unknown)
  HEALTH=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$APP_CID" 2>/dev/null || echo unknown)
  echo "status=$STATUS health=$HEALTH"
  [ "$STATUS" = running ] && ok "App container running" || bad "App container durumu: $STATUS"
  [ "$HEALTH" = healthy ] && ok "App healthcheck healthy" || warn "App healthcheck: $HEALTH"
fi

head "DATABASE CONTENT"
docker compose exec -T postgres psql -U "${POSTGRES_USER:-haberrss}" -d "${POSTGRES_DB:-haberrss}" -c "
SELECT 'news_last_24h' AS metric, COUNT(*) AS value FROM news WHERE published_at >= NOW() - INTERVAL '24 hours'
UNION ALL SELECT 'clusters_total', COUNT(*) FROM story_clusters
UNION ALL SELECT 'clustered_news', COUNT(DISTINCT article_id) FROM cluster_articles
UNION ALL SELECT 'trends_total', COUNT(*) FROM trends;
" 2>/dev/null || true

head "CLUSTER P0"
CLUSTER_COUNT=$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-haberrss}" -d "${POSTGRES_DB:-haberrss}" -Atc "SELECT COUNT(*) FROM story_clusters" 2>/dev/null | tr -d '[:space:]' || echo 0)
NEWS_COUNT=$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-haberrss}" -d "${POSTGRES_DB:-haberrss}" -Atc "SELECT COUNT(*) FROM news" 2>/dev/null | tr -d '[:space:]' || echo 0)
if [ "${NEWS_COUNT:-0}" -gt 0 ] && [ "${CLUSTER_COUNT:-0}" -eq 0 ]; then
  bad "P0: $NEWS_COUNT haber var ama 0 story cluster var"
else
  ok "Cluster durumu: news=$NEWS_COUNT clusters=$CLUSTER_COUNT"
fi

head "GDELT"
if docker compose logs --tail=300 app 2>/dev/null | grep -q "GDELT collector failed"; then
  bad "GDELT son loglarda hata veriyor"
  docker compose logs --tail=300 app 2>/dev/null | grep -E "GDELT|Traceback|ERROR" | tail -30 || true
else
  ok "GDELT son 300 app logunda hata görünmüyor"
fi

head "RECENT ERRORS"
docker compose logs --tail=500 app 2>/dev/null | grep -E "ERROR|Traceback|CRITICAL" | tail -40 || echo "Hata kaydı yok"

head "ENV / SECRETS"
if [ -f .env ]; then
  ok ".env mevcut"
  chmod 600 .env 2>/dev/null || true
  for key in POSTGRES_PASSWORD DATABASE_URL REDIS_URL TELEGRAM_API_ID TELEGRAM_API_HASH TELEGRAM_SESSION GEMINI_API_KEY; do
    if grep -Eq "^${key}=.+" .env 2>/dev/null; then echo "[SET] $key"; else echo "[EMPTY] $key"; fi
  done
else
  bad ".env bulunamadı"
fi

head "SOURCE / COLLECTOR"
docker compose logs --tail=200 app 2>/dev/null | grep -E "collector source=|entries=" | tail -25 || warn "Collector source logu bulunamadı"

head "RESTART / RESOURCE"
docker compose ps 2>/dev/null | sed -n '1,20p'
if docker compose ps 2>/dev/null | grep -q "Restarting"; then bad "En az bir servis restart döngüsünde"; else ok "Restart döngüsü görünmüyor"; fi

head "RESULT"
echo -e "${GREEN}OK: $PASS${NC}  ${YELLOW}WARN: $WARN${NC}  ${RED}FAIL: $FAIL${NC}"
if [ "$FAIL" -gt 0 ]; then
  echo "Öncelik: FAIL kayıtlarını düzelt; özellikle CLUSTER P0 ve GDELT."
  exit 2
fi
if [ "$WARN" -gt 0 ]; then exit 1; fi
exit 0
