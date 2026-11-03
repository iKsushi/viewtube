#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${E2E_BASE_URL:?Set local test deployment URL}"
: "${E2E_MEDIA_FILE:?Set absolute path to a valid short MP4}"
mkdir -p .runtime/browser-host
pnpm --dir .runtime/browser-host add @playwright/test@1.56.1
NODE_PATH="$PWD/.runtime/browser-host/node_modules" E2E_CHROME=1 \
  .runtime/browser-host/node_modules/.bin/playwright test --config e2e/playwright.config.js
