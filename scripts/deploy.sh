#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
APP_URL=http://localhost:8080
DEMO=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --url) APP_URL="${2:?--url needs a URL}"; shift 2 ;;
    --demo) DEMO=true; shift ;;
    *) echo "Usage: bash scripts/deploy.sh [--url http://localhost:8080] [--demo]"; exit 2 ;;
  esac
done
if ! command -v docker >/dev/null 2>&1; then
  [[ -f /etc/os-release ]] || { echo "Install Docker Desktop first, or use Ubuntu 24.04/26.04."; exit 1; }
  . /etc/os-release
  [[ "$ID" == ubuntu ]] || { echo "Automatic Docker installation supports Ubuntu only."; exit 1; }
  SUDO=()
  [[ $EUID -eq 0 ]] || SUDO=(sudo)
  "${SUDO[@]}" apt-get update
  "${SUDO[@]}" apt-get install -y ca-certificates curl python3
  "${SUDO[@]}" install -m 0755 -d /etc/apt/keyrings
  "${SUDO[@]}" curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  "${SUDO[@]}" chmod a+r /etc/apt/keyrings/docker.asc
  ARCH=$(dpkg --print-architecture)
  printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: %s\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' "${UBUNTU_CODENAME:-$VERSION_CODENAME}" "$ARCH" | "${SUDO[@]}" tee /etc/apt/sources.list.d/docker.sources >/dev/null
  "${SUDO[@]}" apt-get update
  "${SUDO[@]}" apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  "${SUDO[@]}" systemctl enable --now docker
fi
DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then
  if [[ "$(uname -s)" == Linux ]] && command -v sudo >/dev/null; then DOCKER=(sudo docker); fi
fi
"${DOCKER[@]}" info >/dev/null
"${DOCKER[@]}" compose version >/dev/null
python3 scripts/configure.py --url "$APP_URL"
"${DOCKER[@]}" compose build
"${DOCKER[@]}" compose up -d --wait --wait-timeout 240
if [[ "$DEMO" == true ]]; then
  # Avoid a race between the foreground seeder and the normal worker.
  "${DOCKER[@]}" compose stop worker
  trap '"${DOCKER[@]}" compose start worker >/dev/null' EXIT
  "${DOCKER[@]}" compose --profile tools run --rm seed
  "${DOCKER[@]}" compose start worker
  trap - EXIT
fi
"${DOCKER[@]}" compose images --format json > .runtime/images.json
"${DOCKER[@]}" compose ps
printf '\nViewTube is ready at %s\nCredentials: .runtime/access.txt\nSwagger: %s/docs\n' "$APP_URL" "$APP_URL"
