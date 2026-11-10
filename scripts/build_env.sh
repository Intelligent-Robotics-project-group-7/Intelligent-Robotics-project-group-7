#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
docker build --tag turtlebot4-research:jazzy .
mkdir -p evidence
docker image inspect turtlebot4-research:jazzy > evidence/built_image.json
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges \
  turtlebot4-research:jazzy bash -lc \
  'source /opt/ros/jazzy/setup.bash; dpkg-query -W' > evidence/packages.lock.tsv
