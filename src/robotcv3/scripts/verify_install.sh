#!/usr/bin/env bash
# Phase 1 sensors and Phase 2 detection only; no robot motion or Phase 3 work.
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
bash scripts/run_env.sh bash -lc \
  'source /opt/ros/jazzy/setup.bash; python3 -m pytest -q tests/test_detection_metrics.py'
bash scripts/run_env.sh bash scripts/run_smoke.sh
bash scripts/run_person_suite.sh
bash scripts/analyze_person_suite.sh
bash scripts/run_env.sh python3 scripts/check_install_results.py
echo 'PASS: scoring tests, stationary sensors, six detection cases, and analysis completed.'
