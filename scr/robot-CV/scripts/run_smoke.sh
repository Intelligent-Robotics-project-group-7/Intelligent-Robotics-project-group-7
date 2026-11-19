#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
set -u
export GZ_IP=127.0.0.1
export LP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=2
if [ -z "${DISPLAY:-}" ]; then
  exec xvfb-run -a -e /workspace/evidence/xvfb.log -s '-screen 0 1280x720x24 -nolisten tcp' bash "$0"
fi
mkdir -p /workspace/evidence
glxinfo -B > /workspace/evidence/renderer.txt
ros2 launch /workspace/launch/static_camera_smoke.launch.py > /workspace/evidence/simulation.log 2>&1 &
sim_pid=$!
cleanup() {
  kill -INT "$sim_pid" 2>/dev/null || true
  for count in {1..10}; do
    kill -0 "$sim_pid" 2>/dev/null || break
    sleep 0.5
  done
  kill -TERM "$sim_pid" 2>/dev/null || true
}
trap cleanup EXIT
python3 /workspace/scripts/capture_sensor_smoke.py --duration 45
