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
docker compose up -d postgres redis bootstrap
docker compose run --rm bootstrap
docker compose up -d app api

echo
printf '%s\n' '=== HABERRSS STATUS ==='
docker compose ps
printf '%s\n' '=== HEALTH ==='
curl -fsS http://127.0.0.1:8080/health || true
echo
printf '%s\n' '=== TOP TRENDS ==='
curl -fsS 'http://127.0.0.1:8080/api/top-trends?limit=10' || true
echo
