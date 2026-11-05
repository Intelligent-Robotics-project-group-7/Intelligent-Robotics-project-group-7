# Compact rescue robot candidate v1 — bilingual-comment edition

Chinese guide: [README_先读我.md](README_先读我.md). Code and configuration explanations use `ZH:` (Chinese) and `EN:` (English).

This candidate implements the team's chosen compact chassis and color stereo pair, with the left camera reused as the RGB input. It uses separate filenames from the original platform. Parameters are initial simulation design values, not calibrated hardware specifications. Gazebo/ROS runtime validation is still required.

## 1. Appearance: SDF first, CAD later

The first version uses SDF boxes, cylinders, and spheres for a yellow equipment shell, dark bumpers, warning stripes, lidar mast, stereo housing, and orange beacon. SolidWorks can be used later for detailed mechanical design or complex surfaces. Exported CAD meshes may replace `visual` geometry; sensor plugins, topics, TF, inertia, and simplified `collision` geometry still require configuration. Appearance geometry can also obstruct cameras or GPU lidar.

## 2. Geometry and reference frame

- Differential drive: two driven wheels and one front ball caster.
- Main body: 0.56 × 0.36 × 0.16 m; center at (0.08, 0, 0.18) m relative to `base_link`.
- Drive-wheel radius 0.10 m, width 0.06 m, center spacing 0.43 m.
- Overall length approximately 0.66 m, including bumper/camera protrusions; width approximately 0.49 m including wheels.
- `base_link`: ground projection midway between the drive wheels; x forward, y left, z up.
- Approximate masses: main assembly 4 kg, each wheel 0.25 kg, caster 0.10 kg. Inertia uses primitive-geometry approximations, not a detailed CAD assembly.
- Local footprint: x ∈ [-0.26, 0.44], y ∈ [-0.26, 0.26] m, plus 0.02 m padding.
- The NavFn global costmap uses a conservative 0.55 m radius circle. It may reject narrow passages that the physical robot could traverse. A planner that considers footprint and orientation may be needed later.

## 3. Initial sensor settings

| Sensor | Configuration | Notes |
|---|---|---|
| LiDAR | 360°, 360 samples, 10 Hz, 0.08–12 m | Gaussian range noise σ = 0.01 m |
| LiDAR mount | (0.03, 0, 0.48) m | Above body accessories; verify self occlusion in Gazebo |
| Left/right cameras | Each 640×480 RGB, 10 Hz, 90° horizontal field of view | Parallel optical axes, two physical viewpoints |
| Stereo baseline B | 0.12 m | Left y = +0.06 m, right y = -0.06 m |
| Camera mounts | x = 0.421 m, z = 0.32 m | Viewpoints just ahead of the camera housing |
| Camera intrinsics | fx = fy = 320 px; cx = 320, cy = 240 px | Ideal pinhole model without distortion |
| Right projection P[3] | -38.4 | -fx × B; left P[3] = 0 |
| IMU | 50 Hz; yaw-rate noise σ = 0.01 rad/s | Optional; not required for the main PF experiment |
| Noisy wheel odometry | Nominally 30 Hz; σv = 0.01 m/s, σω = 0.02 rad/s | ROS node integrates noisy velocity and publishes matching TF |

This bundle provides stereo images, CameraInfo, and optical transforms. It does **not** include a stereo matcher or a validated depth stream. Depth estimation requires `stereo_image_proc` or another matching algorithm, verified timestamps, actual CameraInfo, textured targets, and known-distance checks. For rectified stereo, depth is `Z = fx × B / d`, where `d` is disparity in pixels. If resolution or field of view changes, update K and P consistently for both cameras.

## 4. ROS interfaces and TF ownership

| ROS topic | Purpose |
|---|---|
| `/wheel/odometry_raw` | Raw DiffDrive wheel odometry for diagnostics and the noise node |
| `/wheel/odometry`, `/odom` | Identical noisy integrated odometry outputs |
| `/ground_truth/odom` | Simulator world ground truth for offline evaluation only |
| `/scan`, `/imu/data` | Lidar and IMU measurements |
| `/stereo/left/image_raw`, `/stereo/right/image_raw` | Left/right color images |
| `/stereo/left/camera_info`, `/stereo/right/camera_info` | Camera intrinsics and projection matrices |
| `/camera/image_raw`, `/camera/camera_info` | Aliases of the left-camera data; no third camera |
| `/cmd_vel` | Twist commands sent to the differential drive |

```text
map -> odom                     Exactly one of AMCL / SLAM / custom PF, according to mode
       -> base_link             Published by noisy_odom_node.py
          -> laser_frame
          -> imu_link
          -> stereo_camera_link
             -> left_camera_link  -> left_camera_optical_frame
             -> right_camera_link -> right_camera_optical_frame
```

Camera body axes are x forward, y left, z up; optical axes are x right, y down, z forward. The launch file supplies the conversion. Do not also run the old robot's static transforms.

## 5. Meaning of noisy odometry

The node reads raw wheel-odometry velocity and timestamps, adds independent Gaussian noise and configurable constant biases to v and ω, and integrates the resulting motion. The same integrated state supplies pose, covariance, and `odom -> base_link` TF. This creates accumulated error, instead of adding noise only to velocity while navigation still receives ideal pose/TF.

Raw Gazebo TF is not bridged. Ground truth has zero configured noise and is not used as an online estimator input. Covariance uses first-order propagation; it does not model all contact errors or wheel slip. `seed=42` controls only this node's random samples. Timing, dropped samples, trajectories, and Gazebo sensor randomness also affect repeatability.

## 6. Copy into the Ubuntu package

Copy the folders into:

```text
/home/lucas/Documents/Intelligent Robot/rob_ws/src/learning_pkg_python/
├── models/rescue_robot/car.sdf
├── models/rescue_robot/model.config
├── config/bridge_rescue.yaml
├── config/odom_noise_rescue.yaml
├── config/nav2_rescue.yaml
├── launch/rescue_platform.launch.py
├── learning_pkg_python/noisy_odom_node.py
├── worlds/rescue_navigation_test.sdf
└── maps/rescue_navigation_test.yaml and rescue_navigation_test.pgm
```

These files use new names. `model://rescue_robot` selects the new model directory, while the instance name remains `vehicle_blue` to retain existing Gazebo topic prefixes. The test world retains the previous wall/obstacle layout, so its static occupancy map remains applicable.

## 7. Stage 1: inspect appearance and stability

Stop the old Gazebo, bridge, static TF, localization, and navigation processes. Run:

```bash
source /opt/ros/jazzy/setup.bash
cd "$HOME/Documents/Intelligent Robot/rob_ws"
ros2 launch "$PWD/src/learning_pkg_python/launch/rescue_platform.launch.py" start_bridge:=false
```

Check that the robot settles stably, wheels contact the ground, geometry does not overlap incorrectly, and sensors are unobstructed. The included PNG is a geometry-based design preview, not a Gazebo runtime screenshot.

## 8. Stage 2: verify sensor and odometry interfaces

Stop the stage-1 launch, then run in the same terminal:

```bash
ros2 launch "$PWD/src/learning_pkg_python/launch/rescue_platform.launch.py"
```

This starts Gazebo, bridging, noisy odometry, and all sensor static TF publishers. It does not start SLAM, localization, or navigation. Do not additionally run the old bridge/noise/TF programs. Software rendering is enabled by default; use `software_rendering:=0` if suitable native graphics are available.

In another sourced terminal, check:

```bash
ros2 topic echo /odom --once
ros2 run tf2_ros tf2_echo base_link laser_frame --ros-args -p use_sim_time:=true
ros2 topic echo /scan --field ranges --once --qos-reliability best_effort
ros2 topic echo /stereo/left/camera_info --once --qos-reliability best_effort
ros2 topic echo /stereo/right/camera_info --once --qos-reliability best_effort
ros2 topic echo /stereo/left/image_raw --field header --once --qos-reliability best_effort
ros2 topic echo /stereo/right/image_raw --field header --once --qos-reliability best_effort
```

Stop continuous `tf2_echo` with Ctrl+C before running the next check. Right CameraInfo P[3] should be -38.4 and left P[3] should be 0. Image headers should identify their respective optical frames. Record both streams together to assess synchronization; two sequential `--once` commands cannot establish timestamp agreement. Measure actual frame rates and VM workload.

## 9. Stage 3: revalidate navigation

Only after chassis/sensor checks pass, open three separate terminals, source ROS, and enter the workspace in each. Run:

```bash
ros2 launch nav2_bringup localization_launch.py \
  map:="$PWD/src/learning_pkg_python/maps/rescue_navigation_test.yaml" \
  params_file:="$PWD/src/learning_pkg_python/config/nav2_rescue.yaml" \
  use_sim_time:=true autostart:=true use_composition:=False
```

```bash
ros2 launch nav2_bringup navigation_launch.py \
  params_file:="$PWD/src/learning_pkg_python/config/nav2_rescue.yaml" \
  use_sim_time:=true autostart:=true use_composition:=False
```

```bash
ros2 launch nav2_bringup rviz_launch.py use_sim_time:=true
```

AMCL is used here for fixed-map navigation debugging. The formal custom-PF comparison must replace its map-to-odom publishing responsibility consistently, while holding other experimental conditions constant. Unknown-environment SLAM, target detection, stereo reconstruction, and formal evaluation are separate integration tasks.

## 10. Dependencies and verification limits

Use the installed ROS 2 Jazzy, modern Gazebo, ros_gz_bridge, tf2_ros, Nav2, rclpy, geometry_msgs, and nav_msgs. For a later installed ROS package, declare runtime dependencies in package.xml and install models/worlds/maps/config/launch and Python modules through setup.py. The provided launch file currently resolves resources directly from the source package.

Completed checks: XML parsing, Python syntax, stereo physical-baseline/projection consistency, map pairing, and ZIP integrity. For this bilingual edition, executable Python AST (excluding documentation), SDF element content, active YAML lines, and map pixels are checked against the original candidate. YAML preservation is a text comparison, not a claim of validation by a YAML parser.

Not yet verified: Gazebo loading/dynamics, live ROS bridging, actual CameraInfo values, stereo synchronization/depth, and navigation with the new chassis.

References:

- https://gazebosim.org/docs/harmonic/sensors/
- https://github.com/gazebosim/gz-sensors/blob/gz-sensors8/src/CameraSensor.cc
- https://github.com/gazebosim/sdformat/blob/sdf14/sdf/1.10/camera.sdf
- https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/systems/diff_drive/DiffDrive.cc
