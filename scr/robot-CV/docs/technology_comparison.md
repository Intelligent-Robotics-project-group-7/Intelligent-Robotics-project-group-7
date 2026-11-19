# Technology Comparison and Phase 1 Selection

Date: 2026-11-10. This report records the selection rationale. Phase 2 has added measured CPU 2D detection results; see the [detection report](phase2_detection.md). Physical hardware performance, full acquisition latency, and following performance remain **NOT VERIFIED**.

## Base environment

Selected: **Ubuntu 24.04 container + ROS 2 Jazzy + Gazebo Harmonic**, an [officially supported TurtleBot 4 combination](https://turtlebot.github.io/turtlebot4-user-manual/software/turtlebot4_simulator.html). The host runs Ubuntu 26.04, so ROS/Gazebo are installed inside the container. Jazzy target platforms and support dates are documented in [REP-2000](https://www.ros.org/reps/rep-2000.html#jazzy-jalisco-may-2024-may-2029).

Humble/Ubuntu 22.04/Fortress remains another official option. There is no physical Humble robot to match here, so two environments are unnecessary. Before connecting physical hardware, verify the robot image, base, and driver versions, then decide whether to use Humble. Do not assume DDS interoperability between distributions.

## ROS 2 responsibilities

| Component | Responsibility | Project use |
|---|---|---|
| ROS 2 Jazzy | Nodes, interfaces, tools, and distribution dependencies | Required; current foundation |
| TF2 | Transform camera observations to base/odom/map at observation time | Required; validate before 3D fusion |
| DDS/RMW | Transport, discovery, and QoS; does not replace synchronisation or protection protocols | Use the distribution default and record the implementation; runtime container has no external network |
| Topics | Frequent images, depth, scans, detections, and status | Required; use SensorDataQoS for images and record reliability compatibility |
| Services | Short operations such as setting/clearing targets or querying status | Planned; not for long navigation tasks |
| Actions | Cancellable navigation/following tasks with feedback | Connect to a Mock server first |
| Lifecycle Nodes | Configuration, activation, deactivation, and recovery | Proposed for perception/following coordination; inactive by default |
| Nav2 + Costmap 2D | Global paths, local trajectories, and obstacle costs | Dependencies installed; navigation currently inactive |
| SLAM Toolbox | Mapping and map→odom | Future mapping phase |
| AMCL | Localisation on a known map | Future alternative to SLAM; only one map→odom authority |

## Detection and depth approaches

Accuracy depends on the model, input size, scene/domain differences, and thresholds. Speed depends on compute, preprocessing, postprocessing, and transport. This is an engineering comparison, not a measured ranking.

| Method | Detection and depth | Resources and integration | OAK/current simulation fit | Decision |
|---|---|---|---|---|
| OpenCV DNN + MobileNet/other detectors | Host detection followed by robust measurements from aligned depth ROIs | CPU-capable; requires model handling and message adaptation; performance NOT VERIFIED | Can consume simulated RGB-D; cannot simulate device inference speed | Possible smaller-model baseline |
| Ultralytics YOLO | Multiple model families; boxes/masks support RGB-D lifting | Python/PyTorch or ONNX export; CPU/GPU options; check code and weight terms separately | OAK-independent; CPU is usable in this VM | Do not assume optimality; compare on the same rosbag later |
| Current yolo_ros + ONNX Runtime | C++ plugins for detection/tracking/3D lifting | Community ROS 2 integration; current source differs substantially from old tutorials, requiring a pinned commit | Can consume virtual RGB/depth/CameraInfo | Version 5.0.0 compiled and CPU 2D detection verified; tracking/3D plugins inactive |
| DepthAI SpatialDetectionNetwork | Device detection with stereo depth and spatial measurements | Can reduce host load; constrained by device-supported networks and compiled formats | Strong physical OAK option; no device/VPU here | Not installed during pure simulation; no VPU FPS claim |
| MediaPipe Pose | Body landmarks for pose/action analysis | CPU and selected hardware backends; additional ROS adaptation required | Can process virtual RGB; body coordinates are not absolute camera distance | Not required for Phase 1 |
| NVIDIA Isaac ROS | TensorRT/Triton and accelerated image pipelines | Requires compatible NVIDIA platform, drivers, and storage | No visible CUDA device in this VM | Not installed |

MediaPipe world landmarks have a hip-centred origin and cannot directly measure robot-to-person distance. See the [official source documentation](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/pose.md). Select Isaac ROS 4.0 hardware using its [version-specific documentation](https://nvidia-isaac-ros.github.io/v/release-4.0/repositories_and_packages/isaac_ros_dnn_inference/index.html); arbitrary Jetson models are not compatible with every release.

### DepthAI version requirements

Humble/Jazzy v3 driver packages use the `_v3` suffix. Unsuffixed legacy drivers and v3 documentation are not interchangeable. See the [official explanation](https://docs.luxonis.com/software-v3/depthai/ros/driver). A future physical experiment must record camera model/MXID, RVC generation, USB link, ROS package version, DepthAI library version, model format/compiler, firmware, calibration, synchronisation, and alignment settings. These physical observations are unavailable in this phase.

A virtual RGB-D camera can test ROS interfaces; there is no evidence that it simulates the Myriad X inference engine. A fair physical comparison of DepthAI route A with host route B is **NOT VERIFIED**.

## Tracking and target identity

| Method | ID maintenance | Occlusion/crossing limitations | Current recommendation |
|---|---|---|---|
| Kalman Filter | Predicts state and covariance; no data association by itself | Does not recognise identity; long prediction drifts | Use as a motion model, not as a complete tracker |
| ByteTrack | Confidence-staged association using motion and boxes | Long occlusions and similar crossing trajectories can switch IDs | First lightweight baseline |
| DeepSORT | Motion gating, appearance distance, and matching cascade | Similar clothes/back views and domain differences in old models | Design reference; avoid the entire legacy TensorFlow stack |
| BoT-SORT | Motion, optional appearance, and global camera-motion compensation | ReID adds computation and does not guarantee identity | Comparator for crossings and a moving camera |
| DepthAI ObjectTracker | Device/host tracklets; some versions support spatial association | Spatial use depends on configuration; limited identity guarantees | Evaluate only on the physical route |
| 3D data association | Position/covariance gating in a common odom frame, with appearance and 2D evidence | Depth failures, TF delay, and crowding can still cause mismatches | Add incrementally to a 2D baseline |

Target selection is independent of the tracker. Lock a target with `{session_id, track_id}`; old IDs must not carry over automatically after camera/tracker restarts. Candidate tracks can survive brief occlusion, but target-driven control must stop when observations expire. Reappearance requires consistent spatial, temporal, appearance, and confidence evidence; ambiguity requires explicit reselection. Automatically choosing the nearest person would conceal target loss.

Papers and original implementations are listed in `industry_research.md`. No IDF1, HOTA, or incorrect-switch measurements are available yet.

## Navigation options A and B

| Comparison | A: Nav2 dynamic-target/path updates | B: separate closed-loop following controller |
|---|---|---|
| Advantages | Reuses maps, planners, costmaps, behaviour trees, and task cancellation | Shorter latency path; distance/bearing control is straightforward in open areas |
| Limitations | Frequent target changes can cause replanning oscillation; costs near people require handling | Must add obstacle avoidance, reachability, stopping, arbitration, and recovery; image left/right error alone cannot navigate around obstacles |
| Occlusion/corners | Can use known free space and the last valid position; prediction lifetime still needs limits | Control evidence quickly becomes stale when the target leaves view |
| Protection interface | Output must pass independent speed limits, Collision Monitor, and final enable gating | Requires the same independent protection chain before the base |
| Project choice | Future main approach for complex scenes; validate updates/cancellation through Mock actions first | Open-area comparator; motion output not implemented yet |

Nav2 Jazzy has a dynamic-target behaviour-tree tutorial and dedicated Following Server source. Source availability must be distinguished from installed functionality. See the [official tutorial](https://docs.nav2.org/jazzy/tutorials/general_tutorials/navigation2_dynamic_point_following/navigation2_dynamic_point_following/). Repeatedly sending NavigateToPose is not the only established approach, and the Following Server's default search rotation is not a project default.

Local verification: Nav2 1.3.13 is installed and the `FollowObject` action definition is queryable, but `opennav_following` is absent from the image. The dedicated Following Server is therefore not recorded as runnable. The next integration stage starts with Mock actions and dynamic-target behaviour trees, with separate verification of that optional package.

### Controllers and dynamic obstacles

- Regulated Pure Pursuit: path tracking, speed regulation using curvature/obstacle distance, and forward collision checks. Suitable for constrained compute budgets, but does not replace global planning or complete crowd prediction. [Jazzy source documentation](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_regulated_pure_pursuit_controller/README.md).
- MPPI: samples predicted trajectories and evaluates costs, with additional tuning and compute requirements. Measure the software-rendered VM budget before comparing it with RPP. [Jazzy source documentation](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_mppi_controller/README.md).
- Costmap 2D: static, obstacle, and inflation layers handle map and sensor costs. An obstacle layer does not provide long-term pedestrian behaviour prediction.
- Social navigation: personal space, group relations, and avoiding passage through groups need additional policies. SPENCER offers research experience; standard Nav2 does not automatically guarantee social behaviour.
- Collision Monitor: limits/stops velocity on sensor timeouts and zone triggers. It must be in the final velocity chain and tested through fault injection. [Jazzy parameters](https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/collision_monitor/configuring_collision_monitor_node/).

## Lightweight toolchain

| Priority | Tools | Purpose/current action |
|---|---|---|
| Required | Ubuntu 24 container, ROS 2, Git, CMake/colcon, Python/C++ | Reproducible simulation foundation; retain source and dependency locks |
| Required | Gazebo Harmonic, TurtleBot 4 Simulator, ros_gz | Virtual hardware and message bridging |
| Required | OpenCV/cv_bridge, rosbag2 | Image I/O and reproducible data collection |
| Required, by phase | pytest / launch_testing | Numerical, integration, and disconnection tests; avoid empty tests that merely repeat implementation |
| Recommended | RViz2 | Images, TF, point clouds, and trajectories; may already be included by official simulation dependencies; GUI currently inactive |
| Recommended | Docker | Isolate host 26.04 from Jazzy dependencies; runtime network disabled |
| Recommended | VS Code/Codex, Dev Container configuration | Editing and remote development; no additional desktop IDE installed on the server |
| Optional | Foxglove, PlotJuggler | Larger-scale log/plot analysis; not added in Phase 1 |
| Not currently needed | PyTorch training, CUDA, TensorRT, Isaac Sim, full MediaPipe stack | No training task or compatible GPU; not preinstalled |

Pin the base-image digest, source SHAs, and installed package inventory. The Dockerfile fixes the base image, but apt repositories evolve. Retain this built image/image ID and packages.lock to reuse the observed environment; rebuilding on an arbitrary future date is not guaranteed to produce a byte-identical image.
