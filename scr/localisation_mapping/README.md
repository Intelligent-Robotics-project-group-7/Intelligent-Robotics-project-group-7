# Localisation Mapping – SLAM Toolbox

## Overview

This package implements 2D occupancy-grid mapping for the Group 7 search-and-rescue robotics project using ROS 2 Jazzy, Gazebo and SLAM Toolbox.

The TurtleBot4 uses LiDAR scans and odometry to build a map of an initially unknown indoor environment.

## Features

- SLAM Toolbox integration using asynchronous online mapping.
- 2D occupancy-grid map generation.
- LiDAR scan input.
- Simulation time support.
- Configurable mapping parameters.

## Requirements

- ROS 2 Jazzy
- Gazebo simulation
- TurtleBot4 simulation
- SLAM Toolbox
- Nav2 map server (for saving maps)

## Package Structure

```text
localisation_mapping/
├── config/
│   └── slam_params.yaml
├── launch/
│   └── slam_mapping.launch.py
├── localisation_mapping/
│   ├── __init__.py
│   └── occupancy_grid_mapper.py
├── resource/
├── test/
├── package.xml
├── setup.py
└── README.md
```

## Launching SLAM Mapping

From the team repository root, build the package:

```bash
source /opt/ros/jazzy/setup.bash
colcon build --base-paths scr/localisation_mapping --packages-select localisation_mapping --symlink-install
source install/setup.bash
```

Launch SLAM Toolbox:

```bash
ros2 launch localisation_mapping slam_mapping.launch.py
```

The Gazebo simulation, robot sensors and required TF transforms must already be running.

## ROS 2 Interfaces

| Interface | Type | Purpose |
|---|---|---|
| `/scan` | LaserScan | LiDAR input |
| `/odom` | Odometry | Robot odometry |
| `/map` | OccupancyGrid | Generated 2D map |
| `/tf` | TFMessage | Coordinate transforms |

## SLAM Configuration

The main parameters configured in `config/slam_params.yaml` include:

| Parameter | Value |
|---|---|
| `map_frame` | `map` |
| `odom_frame` | `odom` |
| `base_frame` | `base_link` |
| `scan_topic` | `/scan` |
| `minimum_travel_distance` | `0.1` |
| `minimum_travel_heading` | `0.1` |
| `minimum_time_interval` | `0.2` |
| `max_laser_range` | `12.0` |

## Saving the Map

Once a satisfactory map has been generated, it can be saved using:

```bash
ros2 run nav2_map_server map_saver_cli \
  -f ~/ros2_ws/maps/group7_map \
  --ros-args -p use_sim_time:=true
```

This generates a YAML map metadata file and a PGM occupancy-grid image.
