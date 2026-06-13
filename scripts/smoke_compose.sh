#!/usr/bin/env bash
# Compose smoke check (scaffold for CI gate 8 — wired into CI in a later phase).
# Brings up the default profile, asserts every default service is healthy, and
# verifies the trainer is NOT running on a default up (constitution Art. III).
set -euo pipefail

cd "$(dirname "$0")/.."

[ -f .env ] || { echo "ERROR: .env missing. Run: cp .env.example .env"; exit 1; }

echo "Booting default stack..."
docker compose up -d --build

DEFAULT_SERVICES="postgres redis minio vault backend modelserver worker frontend"
echo "Waiting for services to report healthy..."
deadline=$((SECONDS + 180))
while [ $SECONDS -lt $deadline ]; do
  unhealthy=0
  for svc in $DEFAULT_SERVICES; do
    cid=$(docker compose ps -q "$svc" || true)
    [ -n "$cid" ] || { unhealthy=1; continue; }
    status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo "missing")
    case "$status" in healthy|running) ;; *) unhealthy=1 ;; esac
  done
  [ "$unhealthy" -eq 0 ] && break
  sleep 5
done

# Trainer must be absent on a default up.
if [ -n "$(docker compose ps -q trainer || true)" ]; then
  echo "FAIL: trainer is running on a default up (should be profile-gated)"; exit 1
fi

[ "$unhealthy" -eq 0 ] && echo "OK: all default services healthy; trainer excluded" || {
  echo "FAIL: not all default services healthy"; docker compose ps; exit 1;
}
