#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/container_common.sh"
tb4_check_image
tb4_check_perception
cd "$TB4_PROJECT_DIR"
docker run "${tb4_docker_args[@]}" --network none "$TB4_IMAGE" \
  bash -lc 'source /opt/ros/jazzy/setup.bash
    python3 /workspace/scripts/compare_hog_baseline.py &&
    bash /workspace/scripts/run_offline_benchmark.sh &&
    python3 /workspace/scripts/summarize_person_suite.py &&
    python3 /workspace/scripts/record_perception_provenance.py'
