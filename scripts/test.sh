#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] || python3 scripts/configure.py
DOCKER=(docker)
docker info >/dev/null 2>&1 || DOCKER=(sudo docker)
"${DOCKER[@]}" compose build api
"${DOCKER[@]}" compose --profile tests build tests
trap '"${DOCKER[@]}" compose --profile tests rm -sf test-db >/dev/null' EXIT
"${DOCKER[@]}" compose --profile tests run --rm tests
