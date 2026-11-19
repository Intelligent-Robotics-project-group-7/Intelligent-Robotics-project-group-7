#!/usr/bin/env bash
set -euo pipefail
apt-get update -qq
# Package resolution and download/disk estimates; assume-no deliberately prevents installation.
apt-get --assume-no install --no-install-recommends \
  ros-jazzy-turtlebot4-simulator ros-jazzy-irobot-create-nodes \
  ros-jazzy-cv-bridge ros-jazzy-image-transport ros-jazzy-vision-msgs \
  python3-colcon-common-extensions python3-pytest python3-scipy git cmake \
  xvfb xauth mesa-utils libgl1-mesa-dri
