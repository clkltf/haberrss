#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/opt/haberrss"
REPO="https://github.com/clkltf/haberrss.git"

mkdir -p /opt

if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --all --prune
  git -C "$APP_DIR" reset --hard origin/main
else
  rm -rf "$APP_DIR"
  git clone "$REPO" "$APP_DIR"
fi

cd "$APP_DIR"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created $APP_DIR/.env"
  echo "Edit it before first real run: nano $APP_DIR/.env"
  exit 0
fi

docker compose build --pull
docker compose up -d postgres redis

echo "Waiting for PostgreSQL..."
for i in {1..30}; do
  if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-haber}" -d "${POSTGRES_DB:-haber}" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

docker compose run --rm bootstrap
docker compose up -d app api

echo
echo '=== HABERRSS STATUS ==='
docker compose ps
echo '=== HEALTH ==='
curl -fsS http://127.0.0.1:8080/health || true
echo
echo '=== TOP TRENDS ==='
curl -fsS 'http://127.0.0.1:8080/api/top-trends?limit=10' || true
echo