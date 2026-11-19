#!/usr/bin/env bash
# Run once with sudo on an Ubuntu host. No physical robot drivers are installed.
set -euo pipefail
usage() {
  echo 'Usage: sudo bash scripts/bootstrap_host.sh [--user EXISTING_USER]' >&2
}
target_user="${SUDO_USER:-}"
if [ "${1:-}" = --user ] && [ "$#" -eq 2 ]; then
  target_user="$2"
elif [ "$#" -ne 0 ]; then
  usage
  exit 2
fi
if [ "$(id -u)" -ne 0 ]; then
  usage
  exit 1
fi
if [ -z "$target_user" ] || ! id "$target_user" >/dev/null 2>&1 || [ "$(id -u "$target_user")" -eq 0 ]; then
  echo 'Choose an existing non-root account with sudo, or pass --user explicitly.' >&2
  exit 1
fi
source /etc/os-release
if [ "${ID:-}" != ubuntu ] || { [ "${VERSION_ID:-}" != 24.04 ] && [ "${VERSION_ID:-}" != 26.04 ]; }; then
  echo 'This host installer supports Ubuntu 24.04 and 26.04. See README for prerequisites.' >&2
  exit 1
fi
if [ "$(uname -m)" != x86_64 ]; then
  echo 'The pinned image and CPU validation currently support x86_64 only.' >&2
  exit 1
fi
apt-get update
apt-get install --no-install-recommends -y ca-certificates git python3
# Keep an existing Docker installation, including Docker CE, rather than conflicting with it.
if ! command -v docker >/dev/null 2>&1; then
  apt-get install --no-install-recommends -y docker.io
fi
if [ -d /run/systemd/system ]; then
  systemctl enable --now docker
elif ! docker info >/dev/null 2>&1; then
  echo 'Docker is installed, but no daemon is available. Start Docker before continuing.' >&2
  exit 1
fi
getent group docker >/dev/null || groupadd docker
usermod -aG docker "$target_user"
docker version
echo "Bootstrap complete for $target_user. Log out and back in to activate Docker group membership."
