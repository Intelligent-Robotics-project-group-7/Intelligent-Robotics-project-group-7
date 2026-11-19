#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
source /workspace/research_ws/install/setup.bash
set -u
case_id="${1:?Pass a case ID}"
if [[ ! "$case_id" =~ ^[a-z0-9_]+$ ]]; then
  echo 'Invalid case ID' >&2
  exit 2
fi
export GZ_IP=127.0.0.1 GZ_PARTITION="tb4_research_phase3_$case_id"
export LP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
log_dir="/workspace/downloads/phase3/logs/$case_id"
mkdir -p "$log_dir"
if [ -z "${DISPLAY:-}" ]; then
  exec xvfb-run -a -e "$log_dir/xvfb.log" \
    -s '-screen 0 1280x720x24 -nolisten tcp' bash "$0" "$case_id"
fi
model_args=()
capture_args=()
if [ -n "${TB4_MODEL:-}" ]; then
  python3 /workspace/scripts/person_models.py path "$TB4_MODEL"
  model_args=("model:=$TB4_MODEL")
  capture_args=(--model "$TB4_MODEL")
fi
python3 /workspace/scripts/prepare_person_world.py "$case_id" --phase 3
ros2 launch /workspace/launch/person_detection_eval.launch.py "case:=$case_id" phase:=3 "${model_args[@]}" \
  > "$log_dir/simulation.log" 2>&1 &
sim_pid=$!
cleanup() {
  kill -INT "$sim_pid" 2>/dev/null || true
  sleep 2
  kill -TERM "$sim_pid" 2>/dev/null || true
}
trap cleanup EXIT
python3 /workspace/scripts/capture_depth_case.py "$case_id" "${capture_args[@]}"
