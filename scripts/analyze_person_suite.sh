#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
docker run --rm --init --network none --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 1024 --memory 4g --cpus 4 \
  --mount "type=bind,src=$project_dir,dst=/workspace" turtlebot4-research:jazzy \
  bash -lc 'source /opt/ros/jazzy/setup.bash
    python3 /workspace/scripts/compare_hog_baseline.py &&
    bash /workspace/scripts/run_offline_benchmark.sh &&
    python3 /workspace/scripts/summarize_person_suite.py &&
    python3 /workspace/scripts/record_perception_provenance.py'
