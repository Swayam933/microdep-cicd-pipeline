#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/.." && pwd)"
compose_file="$project_root/docker-compose.yml"
compose=(docker compose -f "$compose_file")

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is unavailable. Install Docker Compose or enable Docker Desktop WSL integration, then verify with: docker compose version" >&2
  exit 1
fi

cleanup() {
  "${compose[@]}" down --remove-orphans
}

echo "== Building and starting services =="
"${compose[@]}" up --build -d
trap cleanup EXIT

echo "== Waiting for both services =="
ready=false
for attempt in {1..30}; do
  if curl --fail --silent http://localhost:8080/healthz >/dev/null &&
     curl --fail --silent http://localhost:8081/healthz >/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  "${compose[@]}" logs
  echo "Services did not become healthy within 30 seconds." >&2
  exit 1
fi

echo "== Smoke test: reserve two seeded items through orders-service =="
response="$(curl --fail --silent --show-error -X POST http://localhost:8080/orders \
  -H "Content-Type: application/json" \
  -d '{"sku":"sku-100","qty":2}')"
printf '%s\n' "$response"
stock="$(curl --fail --silent --show-error http://localhost:8081/stock/sku-100)"
if [[ "$response" != *'"status":"confirmed"'* || "$stock" != *'"available":48'* ]]; then
  echo "Order smoke test returned an unexpected response." >&2
  exit 1
fi

echo "Local smoke test passed."
