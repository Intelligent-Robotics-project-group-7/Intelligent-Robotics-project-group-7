#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
set -u
cat /etc/os-release
timeout 25s ros2 doctor --report || true
gz sim --versions
python3 -c 'import cv2, numpy, rclpy; print("OpenCV", cv2.__version__); print("NumPy", numpy.__version__)'
for package in turtlebot4_gz_bringup turtlebot4_description irobot_create_nodes nav2_bringup rosbag2 vision_msgs opennav_following; do
  ros2 pkg prefix "$package" || true
done
ros2 interface show nav2_msgs/action/FollowObject || true
dpkg-query -W 'ros-jazzy-turtlebot4*' 'ros-jazzy-nav2*' 'ros-jazzy-opennav*' 'ros-jazzy-gz*' 2>/dev/null || true
