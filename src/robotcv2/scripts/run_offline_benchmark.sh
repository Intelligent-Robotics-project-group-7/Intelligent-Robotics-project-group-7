#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
source /workspace/research_ws/install/setup.bash
set -u
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2
ros2 run yolo_ros yolo_node --ros-args -r __ns:=/yolo \
  --params-file /workspace/config/person_detection.yaml -p detection.max_fps:=0 \
  > /workspace/evidence/phase2/offline_detector.log 2>&1 &
detector_pid=$!
python3 /workspace/scripts/person_detection_adapter.py \
  > /workspace/evidence/phase2/offline_adapter.log 2>&1 &
adapter_pid=$!
trap 'kill -INT "$detector_pid" "$adapter_pid" 2>/dev/null || true' EXIT
python3 /workspace/scripts/benchmark_person_pipeline.py
