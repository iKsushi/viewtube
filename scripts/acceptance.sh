#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
mkdir -p .runtime/acceptance
stamp=$(date -u +%Y%m%dT%H%M%SZ)
exec > >(tee ".runtime/acceptance/$stamp.log") 2>&1
printf 'Acceptance UTC: %s\n' "$stamp"
git rev-parse HEAD
git status --short
uname -m
cat /etc/os-release
python3 scripts/test_package.py
bash scripts/test.sh
docker compose exec -T api python -m app.smoke --url http://web --allow-write
bash scripts/e2e.sh
printf 'PASS: automated acceptance completed. Manual and external checks remain separate.\n'
