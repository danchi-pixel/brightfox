#!/usr/bin/env bash
# Install a new version of Učilnica from /opt/ucilnica/incoming/src.tar.gz (called by deploy.ps1).
#   1. backup (database + photos)    2. unpack the new source next to the old one
#   3. build the new image           4. restart; if it isn't healthy within 2 minutes, roll back
#
# Učilnica starts without an Anthropic API key too (Foxy then shows "not set up"), so there is no key
# gate. `update.sh start` skips steps 1-3 and only (re)starts. Messages are plain ASCII on purpose
# (the Windows console garbles UTF-8).
set -euo pipefail
BASE=/opt/ucilnica
cd "$BASE"
mkdir -p scripts data incoming
chmod 700 data

log() { echo "[$(date +%H:%M:%S)] $*"; }

if [ ! -f .env ]; then
  printf 'APP_UID=%s\nAPP_GID=%s\n' "$(id -u)" "$(id -g)" > .env
  chmod 600 .env
fi
[ -f secrets.env ] || install -m 600 /dev/null secrets.env
docker network inspect edge >/dev/null 2>&1 || docker network create edge >/dev/null

if [ "${1:-}" != start ]; then
  if docker compose ps --status running --services 2>/dev/null | grep -qx ucilnica; then
    log "Backing up before updating"
    bash scripts/backup.sh preupdate || log "WARNING: pre-update backup failed (continuing)"
  fi

  log "Unpacking new source"
  rm -rf src.new
  mkdir src.new
  tar -xzf incoming/src.tar.gz -C src.new

  # Keep the current image so we can roll back.
  if docker image inspect ucilnica-app:latest >/dev/null 2>&1; then
    docker tag ucilnica-app:latest ucilnica-app:previous
  fi

  rm -rf src.old
  if [ -d src ]; then mv src src.old; fi
  mv src.new src
  install -m 0644 src/deploy/compose.yaml compose.yaml
  install -m 0755 src/deploy/server/backup.sh scripts/backup.sh
  install -m 0755 src/deploy/server/update.sh scripts/update.sh
  install -m 0755 src/deploy/server/set-anthropic-key.sh scripts/set-anthropic-key.sh

  log "Building the image (this can take a few minutes)"
  if ! docker compose build --pull ucilnica; then
    log "Build FAILED - the running version was not changed"
    rm -rf src
    if [ -d src.old ]; then mv src.old src; fi
    exit 1
  fi
fi

log "Starting Ucilnica"
docker compose up -d --remove-orphans

for _ in $(seq 1 60); do
  state="$(docker inspect --format '{{.State.Health.Status}}' "$(docker compose ps -q ucilnica)" 2>/dev/null || echo unknown)"
  if [ "$state" = healthy ]; then
    log "Done - Ucilnica is healthy"
    if ! grep -q '^ANTHROPIC_API_KEY=sk-ant-' secrets.env; then
      log "Note: no Anthropic API key yet, so Foxy shows 'not set up'. On the PC: deploy\\set-anthropic-key.ps1"
    fi
    # Tidy up: dangling images and build cache not used for a week (the previous image stays for rollback).
    docker image prune -f >/dev/null 2>&1 || true
    docker builder prune -f --filter until=168h >/dev/null 2>&1 || true
    exit 0
  fi
  sleep 2
done

log "Ucilnica did not become healthy - rolling back"
docker compose logs --tail 60 ucilnica || true
if docker image inspect ucilnica-app:previous >/dev/null 2>&1; then
  docker tag ucilnica-app:previous ucilnica-app:latest
  rm -rf src.failed && mv src src.failed && { [ -d src.old ] && mv src.old src || true; }
  if [ -f src/deploy/compose.yaml ]; then install -m 0644 src/deploy/compose.yaml compose.yaml; fi
  docker compose up -d
  log "Rolled back to the previous version (the failed source is in src.failed)"
fi
exit 1
