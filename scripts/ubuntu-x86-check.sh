#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ $(uname -m) == x86_64 ]] || { echo 'BLOCKED: requires an actual x86_64 Ubuntu host'; exit 2; }
. /etc/os-release
[[ $ID == ubuntu ]] || { echo 'BLOCKED: requires Ubuntu'; exit 2; }
[[ ! -e .env ]] || { echo 'Use a fresh checkout without runtime configuration'; exit 2; }
bash scripts/deploy.sh --demo
sudo bash scripts/acceptance.sh
