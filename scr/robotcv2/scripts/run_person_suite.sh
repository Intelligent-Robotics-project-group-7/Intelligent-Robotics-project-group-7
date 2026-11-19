#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/container_common.sh"
tb4_check_image
tb4_check_perception
cd "$TB4_PROJECT_DIR"
cases=("$@")
if [ "${#cases[@]}" -eq 0 ]; then
  cases=(empty single_front single_far_back two_crossing partial_occlusion exit_return)
fi
mkdir -p evidence/phase2
for case_id in "${cases[@]}"; do
  case "$case_id" in
    empty|single_front|single_far_back|two_crossing|partial_occlusion|exit_return) ;;
    *) echo "Unknown evaluation case: $case_id" >&2; exit 2 ;;
  esac
  echo "Running perception case: $case_id"
  docker run "${tb4_docker_args[@]}" --network none "$TB4_IMAGE" \
    bash scripts/run_person_case.sh "$case_id" > "evidence/phase2/${case_id}_console.log" 2>&1
  echo "Finished perception case: $case_id"
done
