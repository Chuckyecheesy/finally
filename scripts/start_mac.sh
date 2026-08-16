#!/usr/bin/env bash
# Build (if needed) and run the FinAlly container. Idempotent.
set -euo pipefail

IMAGE="finally"
CONTAINER="finally"
PORT="${PORT:-8000}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

FORCE_BUILD=false
OPEN_BROWSER=true
for arg in "$@"; do
  case "$arg" in
    --build) FORCE_BUILD=true ;;
    --no-browser) OPEN_BROWSER=false ;;
    -h|--help)
      echo "Usage: $0 [--build] [--no-browser]"
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed or not on PATH." >&2
  exit 1
fi

mkdir -p "$ROOT/db"

if [ ! -f "$ROOT/.env" ]; then
  echo "No .env found — creating one from .env.example."
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Edit $ROOT/.env and set OPENROUTER_API_KEY to enable AI chat."
fi

if $FORCE_BUILD || [ -z "$(docker images -q "$IMAGE" 2>/dev/null)" ]; then
  echo "Building image '$IMAGE'..."
  docker build -t "$IMAGE" "$ROOT"
fi

if [ -n "$(docker ps -q -f "name=^${CONTAINER}$")" ]; then
  echo "Container '$CONTAINER' is already running."
else
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  docker run -d \
    --name "$CONTAINER" \
    -p "${PORT}:8000" \
    --env-file "$ROOT/.env" \
    -v "$ROOT/db:/app/db" \
    "$IMAGE" >/dev/null
  echo "Started container '$CONTAINER'."
fi

URL="http://localhost:${PORT}"
echo "FinAlly is available at ${URL}"

if $OPEN_BROWSER && command -v open >/dev/null 2>&1; then
  open "$URL" || true
fi
