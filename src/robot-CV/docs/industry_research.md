# TurtleBot 4 Person Perception and Following: Established Technologies

Research date: 2026-11-10 (Europe/London). Phase 1: technical research and a simulation development environment.

## Findings and evidence limits

The user has specified that all hardware is virtual. The project uses an Ubuntu 24.04 container, ROS 2 Jazzy, and Gazebo Harmonic. The first step establishes stationary RGB-D, lidar, and TF data paths before comparing detection and tracking methods. Host CPU inference is the current approach. No OAK-D/VPU is accessible, and there is no evidence that VMware exposes NVIDIA CUDA to the guest.

A professional system should separate detection, distance measurement, target identity, motion planning, and execution protection. Drawing a bounding box does not establish reliable following; a track ID does not guarantee identity across arbitrary occlusions. Phase 1 covered research and the base environment. The implemented 2D detector and measurements are documented in the [Phase 2 report](phase2_detection.md); target tracking and autonomous following are not yet implemented.

Evidence labels: **Official support** means explicitly stated in maintainer documentation or source code; **community implementation** means a third-party project; **design recommendation** means a project choice awaiting validation; **NOT VERIFIED** means untested in this environment. Public projects do not establish the internal technology used by every commercial robot.

## Verification method

The GitHub API was used to record each default branch, its latest commit, archive status, and licence metadata. README and licence snapshots were pinned to commits. Full records are in `../evidence/repository_inventory.json`. Maintenance assessments use commit activity; GitHub `updated_at`, which can reflect activity such as stars, is not a maintenance date.

The short SHAs below correspond to full SHAs in that inventory. Download and checksum records are in `../evidence/source_downloads.lock.json`. The downloaded Nav2 source uses the Jazzy branch rather than the default main branch.

## 1. TurtleBot 4 Simulator: official simulation foundation

- Project: [turtlebot/turtlebot4_simulator](https://github.com/turtlebot/turtlebot4_simulator), Apache-2.0.
- Verified revision: Jazzy branch `b7d0f3b97325`; latest default-branch commit dated 2024-10-30; not archived; source package version 2.0.2. An older branch commit does not establish that distribution maintenance has ceased; apt binary versions are recorded separately.
- Architecture: Gazebo physics and rendered sensors, `ros_gz_bridge` conversion to ROS messages, and simulated Create 3 and TurtleBot nodes providing robot interfaces. Navigation and localisation can be launched optionally.
- Hardware: virtual Create 3, OAK RGB-D, and lidar models. Computation runs on the host CPU/GPU; it does not execute the original OAK-D Myriad/VPU firmware.
- ROS: the official manual lists Jazzy/Ubuntu 24.04/Harmonic and Humble/22.04/Fortress. Galactic is no longer supported.
- Reuse: selected as the official simulation foundation. Camera topics, optical frames, clocks, and bridge directions must be checked individually.
- Lesson: retain official descriptions, standard messages, and simulated interfaces; configure project-specific launch/world files. Gazebo depth is not a validated model of physical stereo error.

Sources: [installation and launch](https://turtlebot.github.io/turtlebot4-user-manual/software/turtlebot4_simulator.html), [camera bridge source](https://github.com/turtlebot/turtlebot4_simulator/blob/jazzy/turtlebot4_gz_bringup/launch/ros_gz_bridge.launch.py).

## 2. TurtleBot 4 Examples: early reference for following with the original camera

- Project: [turtlebot/turtlebot4_examples](https://github.com/turtlebot/turtlebot4_examples), Apache-2.0.
- Revision and maintenance: default Galactic branch, `82c8bdfedf71`, latest commit dated 2022-05-25; not archived. This does not establish readiness for modern Jazzy installations.
- Architecture: Mobilenet Spatial Publisher combines detection and stereo depth to publish spatial detections; FollowBot consumes person detections to follow a target.
- Hardware: TurtleBot 4, a physical OAK-D, and the robot computer. The virtual camera has no equivalent on-device inference engine.
- ROS: this default branch targets Galactic; Humble/Jazzy compatibility is **NOT VERIFIED**.
- Reuse: reference for interfaces and workflow. Do not directly run the old following launch or copy its motion control and legacy DepthAI settings.
- Lesson: camera inference can reduce host load, and spatial detections associate RGB detections with depth. A simple following example does not provide complete identity management, obstacle avoidance, or fault recovery.

Source: [pinned README](https://github.com/turtlebot/turtlebot4_examples/blob/82c8bdfedf71d5399cd3eb18d54097557551b274/README.md).

## 3. DepthAI ROS: official perception on OAK devices

- Project: [luxonis/depthai-ros](https://github.com/luxonis/depthai-ros), MIT.
- Revision and maintenance: default develop branch, `3462a2fb92fc`, latest commit dated 2026-11-04; recent activity, not archived. An active development branch does not establish interface stability.
- Architecture: camera pipelines, composable ROS nodes, calibration/TF, RGB-D, and spatial detections. ObjectTracker can accept spatial detections and retain spatial coordinates in tracklets.
- Hardware: an OAK/RVC device and host. Specific original OAK-D Pro/Lite models require separate verification; no such device is available here.
- ROS: official v3 documentation specifies `depthai_ros_driver_v3` and `ros-<distro>-depthai-ros-v3` for Humble/Jazzy. Only Kilted and later use v3 as the unsuffixed default package. Parameters from v2 examples cannot be assumed compatible.
- Reuse: a leading candidate for a future physical OAK-D route. No device driver is installed for this purely virtual phase, and no VPU performance is claimed.
- Lesson: preserve pixel mappings, depth ROIs, calibration, and timestamps throughout the pipeline. Whether tracking uses spatial information depends on version and configuration; an XYZ output alone does not prove XYZ-based association.

Sources: [v3 ROS driver](https://docs.luxonis.com/software-v3/depthai/ros/driver), [ObjectTracker](https://docs.luxonis.com/software-v3/depthai/depthai-components/nodes/object_tracker).

## 4. yolo_ros: community ROS 2 detection and RGB-D lifting

- Project: [mgonzs13/yolo_ros](https://github.com/mgonzs13/yolo_ros).
- Revision and maintenance: `94d2dd500cb2`, latest default-main commit dated 2026-11-04; not archived.
- The current source README describes a C++, ONNX Runtime, and pluginlib pipeline in one process, including detection, tracking, 3D lifting, and debug rendering. Older Python/Ultralytics node tutorials cannot be assumed to describe this version.
- Hardware: RGB or RGB-D input. CPU ONNX Runtime is available; CUDA/TensorRT are optional backends. A dedicated OAK device is not required. Performance on any particular camera/host is **NOT VERIFIED** by this research snapshot.
- ROS: the maintainer lists Humble/Jazzy and other versions. Compilation and plugin validation in this environment were deferred to the perception phase.
- Licence: the verified current repository is MIT. Model weights and exported ONNX files do not thereby become MIT; Ultralytics weights have separate terms. Older online pages showed GPL, so the pinned commit must be checked.
- Reuse: an important candidate for pure simulation. Pinned source was downloaded in Phase 1 without preinstalling a complete model/GPU stack.
- Lesson: separate inference backends from tracking/depth modules, adapt detections to standard interfaces, and avoid copying every image repeatedly between processes.

Sources: [pinned README](https://github.com/mgonzs13/yolo_ros/blob/94d2dd500cb26027ee9c019f4d3a02029ac615cc/README.md), [licence](https://github.com/mgonzs13/yolo_ros/blob/94d2dd500cb26027ee9c019f4d3a02029ac615cc/LICENSE).

## 5. SPENCER: multimodal people tracking on a real mobile robot

- Project: [spencer-project/spencer_people_tracking](https://github.com/spencer-project/spencer_people_tracking).
- Revision and maintenance: master `09b256ba4bc2`, latest default-branch commit dated 2020-09-22; latest repository push dated 2021-02-02; not archived. This is a historical research framework.
- Architecture: RGB-D/monocular/laser detectors, detection fusion, person tracks, and group relations. The public baseline includes nearest-neighbour association, track initiation, and interacting multiple models (IMM). Not every advanced method discussed in papers is publicly implemented.
- Recorded hardware: front and rear Asus Xtion Pro Live cameras, two SICK LMS500 units, and two i7-4700MQ/GeForce 765M laptops connected over gigabit Ethernet. These are SPENCER's records, not evidence of TurtleBot performance.
- ROS: maintainers list ROS 1 Kinetic/Melodic/Noetic; this does not confirm ROS 2 support.
- Licence: most packages are BSD, with exceptions. The root repository API gives no single licence; check each package before reuse.
- Reuse: not directly installable on Jazzy. Adopt lessons about message boundaries, covariance-aware fusion, track confirmation, and group relations rather than porting the entire legacy stack.

Source: [pinned README: architecture and hardware](https://github.com/spencer-project/spencer_people_tracking/blob/09b256ba4bc22c5cae8a5ae88960de1a387cfd7f/README.md).

## 6. Nav2: established ROS 2 navigation and dynamic-target interfaces

- Project: [ros-navigation/navigation2](https://github.com/ros-navigation/navigation2).
- Maintenance: default main `3b7ec4355be9`, latest commit dated 2026-11-10; not archived. Integration uses a pinned Jazzy source revision and recorded apt package versions.
- Architecture: behaviour trees coordinate planner/controller/behaviour servers; costmaps combine laser/depth obstacles; AMCL or SLAM provides localisation; Collision Monitor belongs in the velocity output chain.
- Hardware: camera-brand independent, requiring correctly configured scan/depth data, odometry, TF, and a mobile base. This project uses corresponding virtual sensors.
- ROS: an official ROS 2 stack with Jazzy and Humble branches. Jazzy source includes `opennav_following` and `FollowObject`; availability in installed binaries must be checked separately.
- Licence: the root LICENSE lists Apache-2.0, BSD-3-Clause, LGPL-2.1-or-later, and other terms by package/file. The whole repository cannot be labelled Apache.
- Reuse: selected. Start with a Mock Action Server, then compare dynamic-target behaviour trees with the dedicated Following Server. The latter does not automatically provide complete socially aware global obstacle avoidance.
- Lesson: update targets through navigation capabilities and keep protection independent of visual detection. Default rotation to search for a lost target is inappropriate for this project's current motion-disabled state.

Sources: [Jazzy dynamic-following tutorial](https://docs.nav2.org/jazzy/tutorials/general_tutorials/navigation2_dynamic_point_following/navigation2_dynamic_point_following/), [Jazzy Following package](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_following/opennav_following/package.xml), [Collision Monitor](https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/collision_monitor/configuring_collision_monitor_node/).

## 7–9. Tracking reference implementations

| Project and pinned revision | Algorithm and purpose | Hardware, ROS 2, maintenance, and licence | Reuse assessment |
|---|---|---|---|
| [ByteTrack](https://github.com/FoundationVision/ByteTrack), `d1bf0191adff` | Two-stage association of high- and low-confidence detections, using motion prediction to recover weak detections; no reliable identity guarantee across long occlusions | The original complete detection pipeline involves a GPU/detector; association can be separated. No official ROS 2 distribution statement. Default-branch commit dated 2022-12-11; MIT; not archived | Start with a lightweight baseline; do not transfer the paper's V100 FPS to this VM |
| [BoT-SORT](https://github.com/NirAharon/BoT-SORT), `251985436d67` | Motion, appearance, camera-motion compensation, and an improved Kalman state; ReID needs a separate model | README testing used Ubuntu 20.04; original implementation depends on PyTorch/related detectors. ROS 2 support unverified. Default-branch commit dated 2022-10-30; MIT; not archived | Reference for camera-motion compensation and appearance fusion; measure whether it reduces ID switches here |
| [DeepSORT](https://github.com/nwojke/deep_sort), `f08cf1dc470e` | Kalman filtering, gating, matching cascade, and appearance embeddings combine motion and appearance for association | Original feature extraction includes TensorFlow; association is camera independent. No ROS 2 distribution statement. The 2025-03-02 default-branch commit corrects text and does not demonstrate ongoing algorithm development; GPL-3.0 | Reference for association, track lifetime, and occlusion handling; do not install the entire old TensorFlow stack into Jazzy |

Papers: [ByteTrack, ECCV 2022](https://arxiv.org/abs/2110.06864), [BoT-SORT, 2022](https://arxiv.org/abs/2206.14651), [DeepSORT, 2017](https://arxiv.org/abs/1703.07402). This project has not reproduced their leaderboard results.

## Applying these methods to this project

1. **Sensor roles:** RGB provides class/appearance information, depth provides scale, and lidar supports obstacle avoidance and localisation. A lidar obstacle is not automatically a person; background depth at a 2D box centre is not a valid person-distance measurement.
2. **Fusion prerequisites:** verify CameraInfo, RGB/depth alignment, exposure/simulation timestamps, and TF extrinsics before fusion in a common frame. Visual identity tracks and obstacle costmaps may update independently.
3. **Stable identity:** use session-scoped IDs for confirmed tracks, explicitly select the target, and retain appearance, position, and uncertainty. Use 3D gating and appearance during crossings; stop and await confirmation when identity is ambiguous.
4. **Occlusion and leaving view:** allow limited prediction, but prediction is not a new observation. Stop target-driven control at timeout and do not automatically choose the nearest person. Turning corners requires a map/local obstacle avoidance, not just image-based left/right steering.
5. **Navigation:** derive reachable goals in free space with a stand-off distance, limit update rates, and smooth goals. Use Nav2 goal updates rather than cancelling and recreating the entire action every frame.
6. **Validation:** fix scenes, trajectories, seeds, models, and weights; measure wall-clock latency and simulation real-time factor; store simulator ground truth independently of the evaluated algorithm. Real-world generalisation, depth holes, and physical VPU performance remain **NOT VERIFIED**.

Commercial deployment also commonly requires redundancy, diagnostics, and a stopping chain informed by risk assessment. The reviewed public material does not establish any particular vendor's internal sensors or safety rating. Collision Monitor is a software protection component, not a replacement for physical robot safety hardware.
