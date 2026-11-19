#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
source /workspace/research_ws/install/setup.bash
set -u
export GZ_IP=127.0.0.1 LP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2
case_id="${1:-single_front}"
mkdir -p "/workspace/evidence/phase2/$case_id"
if [ -z "${DISPLAY:-}" ]; then
  exec xvfb-run -a -e "/workspace/evidence/phase2/$case_id/xvfb.log" \
    -s '-screen 0 1280x720x24 -nolisten tcp' bash "$0" "$case_id"
fi
python3 /workspace/scripts/prepare_person_world.py "$case_id"
ros2 launch /workspace/launch/person_detection_eval.launch.py "case:=$case_id" \
  > "/workspace/evidence/phase2/$case_id/simulation.log" 2>&1 &
sim_pid=$!
cleanup() {
  kill -INT "$sim_pid" 2>/dev/null || true
  sleep 2
  kill -TERM "$sim_pid" 2>/dev/null || true
}
trap cleanup EXIT
python3 /workspace/scripts/collect_person_detection.py "$case_id"
