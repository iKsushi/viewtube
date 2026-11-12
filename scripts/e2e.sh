#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
# Run only against this local test deployment. Accounts and videos are retained.
APP_ORIGIN=$(sed -n 's/^APP_ORIGIN=//p' .env)
[[ "$APP_ORIGIN" == http://localhost:* || "$APP_ORIGIN" == http://127.0.0.1:* ]] || { echo 'E2E requires a local HTTP test deployment'; exit 1; }
mkdir -p .runtime/e2e-media .runtime/e2e-results
docker compose exec -T api ffmpeg -v error -f lavfi -i 'color=c=blue:s=320x180:r=15:d=3' -c:v libx264 -pix_fmt yuv420p -movflags frag_keyframe+empty_moov -f mp4 pipe:1 > .runtime/e2e-media/sample.mp4
docker build -t viewtube-e2e:local e2e
docker run --rm --network host --ipc=host -e E2E_BASE_URL="$APP_ORIGIN" -e E2E_EMULATED="${E2E_EMULATED:-0}" -v "$PWD/.runtime/e2e-media:/media:ro" -v "$PWD/.runtime/e2e-results:/tests/test-results" viewtube-e2e:local npx playwright test "$@"
