#!/usr/bin/env bash
# Host-side download only; no rebuild and no runtime-network changes.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/container_common.sh"
tb4_check_image
cd "$TB4_PROJECT_DIR"
docker run "${tb4_docker_args[@]}" --network bridge "$TB4_IMAGE" \
  python3 scripts/person_models.py download "$@"
