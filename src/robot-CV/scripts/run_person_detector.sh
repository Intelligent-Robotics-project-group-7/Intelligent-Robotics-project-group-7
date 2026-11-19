#!/usr/bin/env bash
# Container-side detector for an existing RGB topic; does not launch a simulator.
set -eo pipefail
source /opt/ros/jazzy/setup.bash
source /workspace/research_ws/install/setup.bash
set -u
model_args=()
if [ "$#" -gt 0 ]; then
  model_args=("$1")
  shift
fi
model_path="$(python3 /workspace/scripts/person_models.py path "${model_args[@]}")"
exec ros2 run yolo_ros yolo_node --ros-args -r __ns:=/yolo \
  --params-file /workspace/config/person_detection.yaml \
  -p "detection.model_path:=$model_path" "$@"
