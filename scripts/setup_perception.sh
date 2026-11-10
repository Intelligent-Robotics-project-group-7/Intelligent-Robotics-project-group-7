#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
python3 scripts/prepare_phase2_assets.py
mkdir -p evidence/phase2
docker image inspect turtlebot4-research:jazzy > evidence/phase2/base_image.json
docker run --rm --init --cpus 4 --memory 4g \
  --mount "type=bind,src=$project_dir,dst=/workspace" \
  turtlebot4-research:jazzy bash scripts/build_perception.sh
