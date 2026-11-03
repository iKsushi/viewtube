#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ ${1:-} == --replace && -n ${2:-} ]] || { echo "Usage: bash scripts/restore.sh --replace /absolute/backup-directory"; exit 2; }
SOURCE=$(cd "$2" && pwd)
python3 - "$SOURCE" <<'PY'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]); expected=json.loads((p/'sha256.json').read_text())
for name in ('database.dump','media.tar.gz'):
 with (p/name).open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
 if actual!=expected[name]: raise SystemExit(f'Checksum mismatch: {name}')
print('Backup checksums verified')
PY
DOCKER=(docker)
docker info >/dev/null 2>&1 || DOCKER=(sudo docker)
"${DOCKER[@]}" compose stop web api worker
# On failure leave writers stopped so a partial restore is not served.
"${DOCKER[@]}" compose exec -T db pg_restore -U viewtube -d viewtube --clean --if-exists --no-owner --exit-on-error < "$SOURCE/database.dump"
gzip -dc "$SOURCE/media.tar.gz" | "${DOCKER[@]}" compose run --no-deps --rm -T api python -m app.backup import
"${DOCKER[@]}" compose exec -T db psql -U viewtube -d viewtube -c 'DELETE FROM sessions;'
"${DOCKER[@]}" compose start api worker web
printf 'Restore complete; previous login sessions invalidated.\n'
