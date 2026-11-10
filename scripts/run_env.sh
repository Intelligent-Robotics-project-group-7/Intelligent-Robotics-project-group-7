#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec docker run --rm --init -it --network none --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 1024 --memory 4g --cpus 4 \
  --shm-size 512m --mount "type=bind,src=$project_dir,dst=/workspace" \
  turtlebot4-research:jazzy "$@"
