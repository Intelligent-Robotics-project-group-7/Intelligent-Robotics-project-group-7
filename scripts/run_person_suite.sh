#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
cases=("$@")
if [ "${#cases[@]}" -eq 0 ]; then
  cases=(empty single_front single_far_back two_crossing partial_occlusion exit_return)
fi
mkdir -p evidence/phase2
for case_id in "${cases[@]}"; do
  echo "Running perception case: $case_id"
  docker run --rm --init --network none --name "tb4-phase2-$case_id" \
    --cap-drop ALL --security-opt no-new-privileges --pids-limit 1024 \
    --memory 4g --cpus 4 --shm-size 512m \
    --mount "type=bind,src=$project_dir,dst=/workspace" turtlebot4-research:jazzy \
    bash scripts/run_person_case.sh "$case_id" > "evidence/phase2/${case_id}_console.log" 2>&1
  echo "Finished perception case: $case_id"
done
