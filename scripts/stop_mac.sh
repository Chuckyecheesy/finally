#!/usr/bin/env bash
# Stop and remove the FinAlly container. Data in ./db is left untouched.
set -euo pipefail

CONTAINER="finally"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed or not on PATH." >&2
  exit 1
fi

if [ -n "$(docker ps -aq -f "name=^${CONTAINER}$")" ]; then
  docker rm -f "$CONTAINER" >/dev/null
  echo "Stopped and removed container '$CONTAINER'. Database in ./db is preserved."
else
  echo "Container '$CONTAINER' is not running."
fi
