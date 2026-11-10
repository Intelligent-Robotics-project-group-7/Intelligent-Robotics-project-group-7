#!/usr/bin/env bash
# Run once on the specified Ubuntu VM with sudo. No robot drivers are installed.
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then
  echo 'Run: sudo bash scripts/bootstrap_host.sh' >&2
  exit 1
fi
target_user="${SUDO_USER:-john}"
if [ "$target_user" != john ]; then
  echo 'This reviewed bootstrap is scoped to the john account.' >&2
  exit 1
fi
apt-get update
apt-get install --no-install-recommends -y docker.io
systemctl enable --now docker
usermod -aG docker "$target_user"
docker version
echo 'Bootstrap complete. Reconnect SSH to activate Docker group membership.'
