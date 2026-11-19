#!/usr/bin/env bash
# Shared host-side settings; /workspace is the container mount, not a host path.
TB4_PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TB4_IMAGE="${TB4_IMAGE:-turtlebot4-research:jazzy}"

tb4_check_docker() {
  if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
    echo 'Use an x86_64 Linux host; see the supported Ubuntu setup in README.' >&2
    return 1
  fi
  if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    echo 'Docker is unavailable. Run the host bootstrap, then log out and back in.' >&2
    return 1
  fi
  if [[ "$TB4_PROJECT_DIR" == *,* ]]; then
    echo 'Docker bind-mount paths cannot contain a comma. Choose another clone directory.' >&2
    return 1
  fi
}

tb4_check_image() {
  tb4_check_docker || return
  if ! docker image inspect "$TB4_IMAGE" >/dev/null 2>&1; then
    echo "Missing image $TB4_IMAGE. Run: bash scripts/build_env.sh" >&2
    return 1
  fi
}

tb4_check_perception() {
  if [ ! -f "$TB4_PROJECT_DIR/research_ws/install/setup.bash" ]; then
    echo 'Perception overlay is missing. Run: bash scripts/setup_perception.sh' >&2
    return 1
  fi
}

# Match file ownership to the caller, including accounts whose UID is not 1000.
# HOME is writable even when that numeric UID has no passwd entry in the image.
tb4_docker_args=(--rm --init --user "$(id -u):$(id -g)"
  --env HOME=/tmp --env ROS_HOME=/tmp/.ros --env GZ_HOMEDIR=/tmp/.gz
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 1024
  --memory 4g --cpus 4 --shm-size 512m
  --mount "type=bind,src=$TB4_PROJECT_DIR,dst=/workspace")
