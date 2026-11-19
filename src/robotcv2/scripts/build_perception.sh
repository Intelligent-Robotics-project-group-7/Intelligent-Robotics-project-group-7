#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
set -u
cd /workspace/research_ws
export CMAKE_BUILD_PARALLEL_LEVEL=2
colcon build --parallel-workers 2 --cmake-args \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
  -DONNX_GPU=OFF -DONNXRUNTIME_VERSION=1.20.0
