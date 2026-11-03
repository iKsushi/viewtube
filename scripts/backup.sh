#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd "$(dirname "$0")/.."
DEST=${1:-"backups/$(date -u +%Y%m%dT%H%M%SZ)"}
[[ ! -e "$DEST" ]] || { echo "Backup destination already exists"; exit 1; }
mkdir -p "$DEST"
DEST=$(cd "$DEST" && pwd)
DOCKER=(docker)
docker info >/dev/null 2>&1 || DOCKER=(sudo docker)
"${DOCKER[@]}" compose stop web api worker
trap '"${DOCKER[@]}" compose start api worker web >/dev/null' EXIT
"${DOCKER[@]}" compose exec -T db pg_dump -U viewtube -d viewtube -Fc > "$DEST/database.dump"
"${DOCKER[@]}" compose run --no-deps --rm -T api python -m app.backup export | gzip > "$DEST/media.tar.gz"
"${DOCKER[@]}" compose images --format json > "$DEST/images.json"
python3 - "$DEST" <<'PY'
import hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]); hashes={}
for name in ('database.dump','media.tar.gz'):
 with (p/name).open('rb') as f: hashes[name]=hashlib.file_digest(f,'sha256').hexdigest()
(p/'sha256.json').write_text(json.dumps(hashes,indent=2))
PY
printf 'Consistent backup saved to %s\n' "$DEST"
