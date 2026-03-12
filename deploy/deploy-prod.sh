#!/bin/bash
# Production deployment — run on the droplet or via CI/CD
set -e

APP_DIR="/opt/talkvault"
cd "$APP_DIR"

echo "Pulling latest code..."
git pull origin main || echo "Not a git repo or no remote"

echo "Building..."
docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml --env-file .env down
docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml --env-file .env up -d --build

echo "Cleaning up..."
docker builder prune -af >/dev/null 2>&1
docker image prune -af >/dev/null 2>&1

echo "Status:"
docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose.prod.yml ps

echo "Done."
