#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/container_common.sh"
tb4_check_image
tb4_check_perception
cd "$TB4_PROJECT_DIR"
cases=("$@")
if [ "${#cases[@]}" -eq 0 ]; then
  names=$(docker run "${tb4_docker_args[@]}" --network none "$TB4_IMAGE" \
    python3 scripts/prepare_person_world.py --phase 3 --list)
  mapfile -t cases <<< "$names"
fi
for case_id in "${cases[@]}"; do
  printf 'Capturing depth case %s\n' "$case_id"
  docker run "${tb4_docker_args[@]}" --network none --env "TB4_MODEL=${TB4_MODEL:-}" "$TB4_IMAGE" \
    bash scripts/run_depth_case.sh "$case_id"
done
