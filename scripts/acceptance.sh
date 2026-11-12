#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
mkdir -p .runtime/acceptance
stamp=$(date -u +%Y%m%dT%H%M%SZ)
exec > >(tee ".runtime/acceptance/$stamp.log") 2>&1
printf 'Acceptance UTC: %s\n' "$stamp"
git -c safe.directory="$PWD" rev-parse HEAD
git -c safe.directory="$PWD" status --short
uname -m
cat /etc/os-release
python3 scripts/test_package.py
python3 scripts/test_e2e_report.py
bash scripts/test.sh
docker compose exec -T api python -m app.smoke --url http://web --allow-write
bash scripts/e2e.sh
python3 scripts/check_e2e_report.py .runtime/e2e-results/report.json
printf 'PASS: automated acceptance completed. Manual and external checks remain separate.\n'
