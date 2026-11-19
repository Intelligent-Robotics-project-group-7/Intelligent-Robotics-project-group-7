#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/container_common.sh"
tb4_check_image
cd "$TB4_PROJECT_DIR"
# Use container Python 3.12 instead of requiring a particular host Python version.
docker run "${tb4_docker_args[@]}" --network bridge "$TB4_IMAGE" \
  python3 scripts/prepare_phase2_assets.py
mkdir -p evidence/phase2
docker image inspect "$TB4_IMAGE" > evidence/phase2/base_image.json
docker run "${tb4_docker_args[@]}" --network bridge \
  "$TB4_IMAGE" bash scripts/build_perception.sh
