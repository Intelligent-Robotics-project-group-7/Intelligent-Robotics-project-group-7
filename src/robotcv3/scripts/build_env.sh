#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/container_common.sh"
tb4_check_docker
cd "$TB4_PROJECT_DIR"
# Additional Docker build flags, such as --no-cache --pull, are passed through.
docker build "$@" --tag "$TB4_IMAGE" .
mkdir -p evidence
docker image inspect "$TB4_IMAGE" > evidence/built_image.json
docker run "${tb4_docker_args[@]}" --network none \
  "$TB4_IMAGE" bash -lc \
  'source /opt/ros/jazzy/setup.bash; dpkg-query -W' > evidence/packages.lock.tsv
