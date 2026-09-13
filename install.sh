#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/opt/haberrss"
REPO="https://github.com/clkltf/haberrss.git"

log(){ printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
fail(){ echo "\nKURULUM HATASI: $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || fail "Bu script root olarak çalıştırılmalı."

log "Gerekli paketler kontrol ediliyor..."
apt-get update -y
apt-get install -y git ca-certificates curl openssl

if ! command -v docker >/dev/null 2>&1; then
  log "Docker kuruluyor..."
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

docker compose version >/dev/null 2>&1 || fail "Docker Compose kullanılamıyor."

if [[ -d "$APP_DIR/.git" ]]; then
  log "Mevcut HaberRSS güncelleniyor..."
  git -C "$APP_DIR" fetch origin main
  git -C "$APP_DIR" reset --hard origin/main
else
  log "HaberRSS GitHub'dan indiriliyor..."
  rm -rf "$APP_DIR"
  git clone --depth 1 "$REPO" "$APP_DIR"
fi

cd "$APP_DIR"

if [[ ! -f .env ]]; then
  log "İlk kurulum ayarları alınıyor..."
  read -rp "Telegram Bot Token (yoksa Enter): " TELEGRAM_BOT_TOKEN
  read -rp "Telegram Chat ID (yoksa Enter): " TELEGRAM_CHAT_ID
  read -rp "Gemini API Key (yoksa Enter): " GEMINI_API_KEY

  DB_PASSWORD="$(openssl rand -hex 24)"
  ADMIN_TOKEN="$(openssl rand -hex 32)"

  cat > .env <<EOF
POSTGRES_DB=haberrss
POSTGRES_USER=haberrss
POSTGRES_PASSWORD=$DB_PASSWORD
DATABASE_URL=postgresql://haberrss:$DB_PASSWORD@postgres:5432/haberrss
REDIS_URL=redis://redis:6379/0
GEMINI_API_KEY=$GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID
ADMIN_TOKEN=$ADMIN_TOKEN
SCAN_INTERVAL_SECONDS=20
TREND_INTERVAL_SECONDS=5
SIGNAL_INTERVAL_SECONDS=30
SOURCE_TIMEOUT_SECONDS=8
MAX_ARTICLES_PER_SOURCE=100
PUBLISH_MODE=manual
AUTO_PUBLISH_SCORE=92
ALERT_SCORE=75
LOG_LEVEL=INFO
EOF
  chmod 600 .env
else
  log ".env mevcut; gizli ayarlar korunuyor."
fi

log "Compose doğrulanıyor..."
docker compose config >/dev/null

log "Servisler kuruluyor..."
docker compose down --remove-orphans || true
docker compose build --pull
docker compose up -d

log "Servislerin sağlığı bekleniyor..."
for i in {1..30}; do
  PG_OK=0; REDIS_OK=0; APP_OK=0
  docker compose exec -T postgres pg_isready -U "$(grep '^POSTGRES_USER=' .env | cut -d= -f2-)" -d "$(grep '^POSTGRES_DB=' .env | cut -d= -f2-)" >/dev/null 2>&1 && PG_OK=1 || true
  docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG && REDIS_OK=1 || true
  docker compose ps --status running --services 2>/dev/null | grep -qx app && APP_OK=1 || true
  if [[ $PG_OK -eq 1 && $REDIS_OK -eq 1 && $APP_OK -eq 1 ]]; then break; fi
  sleep 2
done

log "Son durum:"
docker compose ps

echo
echo "========================================"
echo "        HABERRSS KURULUM TAMAM"
echo "========================================"
echo "GitHub : $REPO"
echo "Dizin  : $APP_DIR"
echo "Servis : app + postgres + redis"
echo
echo "Loglar:"
echo "  cd $APP_DIR && docker compose logs -f app"
echo
echo "Durum:"
echo "  cd $APP_DIR && docker compose ps"
echo "========================================"
