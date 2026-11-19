#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/container_common.sh"
tb4_check_image
tb4_check_perception
cd "$TB4_PROJECT_DIR"
cases=("$@")
if [ "${#cases[@]}" -eq 0 ]; then
  cases=(two_crossing partial_occlusion torso_occlusion exit_return)
fi
for case_id in "${cases[@]}"; do
  printf 'Capturing tracking case %s\n' "$case_id"
  docker run "${tb4_docker_args[@]}" --network none --env "TB4_MODEL=${TB4_MODEL:-}" "$TB4_IMAGE" \
    bash scripts/run_tracking_case.sh "$case_id"
done
