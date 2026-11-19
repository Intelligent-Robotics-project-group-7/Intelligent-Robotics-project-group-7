#!/usr/bin/env bash
# Run as the normal user after the host bootstrap and a new login.
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$(id -u)" -eq 0 ]; then
  echo 'Run this script as your normal Docker-enabled user, without sudo.' >&2
  exit 1
fi
bash "$project_dir/scripts/build_env.sh" "$@"
bash "$project_dir/scripts/setup_perception.sh"
echo 'Installation complete. Run: bash scripts/verify_install.sh'
