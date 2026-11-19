# Executed Checks and Test Records

Date: 2026-11-10 (Europe/London). Scope: the Phase 1 base environment and subsequent Phase 2 2D person detection.

## Initial read-only inspection

Executed over `ssh -o BatchMode=yes john@192.168.48.135`: `hostname`, `/etc/os-release`, `uname`, `nproc`, `free -h`, `df -h`, `lspci`, `lsusb`, and checks of ROS paths, processes, and tools.

Results: SSH succeeded. The host was Ubuntu 26.04.1 on VMware with 8 vCPUs, 7.2GiB RAM, and approximately 15G initial free disk space. No ROS installation, OAK-D, or existing TurtleBot workspace was found. The user subsequently confirmed that all hardware would be virtual.

`sudo -n true` required interactive authentication; the rootless user-namespace check also failed. Authentication was not bypassed. The user ran the prepared Docker installation script in their own SSH terminal. A new connection then confirmed john's docker-group membership and Docker server/client version 29.1.3.

## Research and downloads

The GitHub API was used to verify nine projects, recording branches, commit dates, SHAs, licences, and archive status. Pinned TurtleBot Simulator, Nav2 Jazzy, and yolo_ros source archives were downloaded successfully; hashes are in `../evidence/source_downloads.lock.json`. At this Phase 1 point, downloading source did not mean yolo_ros had been compiled or a model tested; Phase 2 results follow below.

Compressed layers of the official `ros:jazzy-ros-base-noble` linux/amd64 image totalled 296,615,261 bytes; the offline Docker archive was 912,240,640 bytes. The manifest and each layer's SHA-256 were verified. Archive SHA-256: `8411722b407e385760a6d450ef2731f29fa3b078b72501b51061c2052f89a339`. Docker load succeeded.

## Dependency budget and build

Executed in the base image: `apt-get update`, then `apt-get --assume-no install --no-install-recommends ...` for the Dockerfile package list.

Dependency resolution succeeded: 1 package upgrade, 1068 new packages, and no removals. The download budget was 652MB and additional installed disk space was 3269MB. `--assume-no` returned 1 and cancelled installation as expected; this was not a build failure. The reviewed official simulation dependencies were then installed through `bash scripts/build_env.sh`.

Build result: PASS. Image `turtlebot4-research:jazzy` has ID `sha256:40ff6b2de422b7c143d393aef97b4ec5c2b4eaccd1ac50f5d37fb9fcb4f6d11a`. The installed package inventory is saved in `../evidence/packages.lock.tsv`.

Verified container: Ubuntu 24.04.5, ROS 2 Jazzy, Gazebo Sim 8.15.0 (Harmonic), OpenCV 4.6.0, NumPy 1.26.4, and default RMW `rmw_fastrtps_cpp`. Package versions include TurtleBot 4 Simulator 2.0.2, Description 2.1.1, Create 3 packages 3.0.4, and Nav2 1.3.13. Base and simulation packages have independent release schedules; a single repository version cannot establish all installed versions.

In the network-isolated environment, `ros2 doctor --report` could not complete parts of the online Package/Rosdistro reports. This limitation was recorded; the complete doctor report is not described as passing every check. The `FollowObject` interface exists, but `ros2 pkg prefix opennav_following` reported the package absent.

Rendering verification: Xvfb virtual display, Mesa llvmpipe, OpenGL 4.5, `Accelerated: no`. No hardware GPU acceleration or VPU was used.

## Stationary virtual-sensor smoke test: PASS

Final record: 2026-11-10 20:46:15 UTC, also local London time that day. The observation window was 45.000 seconds, using a fully local geometric world and the official TurtleBot 4 standard model, without human assets or a detection model. Container exit code: 0. All nine data-path checks passed.

Command executed from the server project directory:

```bash
docker run --rm --init --name tb4-step1-smoke --network none --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 1024 --memory 4g --cpus 4 \
  --shm-size 512m \
  --mount type=bind,src=/home/john/projects/turtlebot4_person_following,dst=/workspace \
  turtlebot4-research:jazzy bash scripts/run_smoke.sh
```

Raw records: `../evidence/sensor_smoke.json`, `simulation.log`, `smoke_console.log`, and `renderer.txt`. Rates below use the first-to-last reception interval, excluding startup before the first message. They are not detector inference FPS.

| Data | Measurement | Assessment |
|---|---|---|
| RGB | 715 frames, 320×240, rgb8, approximately 18.07Hz wall-clock | PASS: valid images received |
| Depth | 712 frames, 320×240, 32FC1 in metres, approximately 17.99Hz wall-clock | PASS: valid depth received |
| CameraInfo | 715 messages; fx≈fy≈221.765, cx=160, cy=120 | PASS: positive intrinsics consistent with image dimensions |
| LaserScan | 1473 messages, approximately 37.43Hz between first and last reception | PASS: scan messages received; physical scan frequency unverified |
| Clock | 23570 messages spanning 23.569 simulated seconds | PASS: simulation clock advanced |
| TF | base_link to oakd_rgb_camera_optical_frame was queryable | PASS: camera-to-base transform; does not establish map→odom localisation |
| RGB to nearest-depth stamp difference | Median 0ms; P95 0ms | Matching-stamp depth exists in these data; not independent exposure/calibration validation |
| Final depth frame | Positive finite fraction 72.11%; centre 11×11 ROI median 2.95809m | One reference-plane measurement, not a person-localisation or depth-accuracy experiment |

Camera source-time rates were approximately 30.2–30.3Hz, while wall-clock reception was only approximately 18Hz. The observed simulation-time/wall-time ratio was approximately 0.58–0.60. Approximately 30Hz in simulation time cannot be reported as real-time 30FPS. Software rendering under the 4-CPU limit consumes part of the future CPU inference budget.

One runtime `docker stats` snapshot showed CPU 298.41% (approximately 2.98 logical CPUs), 747.5MiB memory, 151 processes/threads, and zero container network I/O. This is not a peak, time average, or long-term stability result. See `../evidence/smoke_resources.json`. The host root disk had approximately 7.4G free at the end.

Screenshots: [RGB](../evidence/camera_rgb.png), [depth visualisation](../evidence/camera_depth_0_to_5m.png). Depth colours span 0–5m; black indicates invalid depth. The geometric plane in the image is not a recognised person.

This test established only the sensor path. It published no navigation goals or velocity commands and loaded neither following services nor Nav2. The temporary simulation container stopped afterwards; the environment image and project files were retained. Gazebo control hardware included in the URDF initialised, but following/path controllers were not activated.

## Issues encountered

- Some ROS/Nav2 pages were restricted or old paths returned 404. Verification used official GitHub source, matching Jazzy documentation, and package inventories instead; no findings were invented from inaccessible pages.
- Nested SSH quoting once caused a syntax error in a read-only Python network check. Uploading scripts for execution resolved this; GitHub downloads succeeded.
- During the build, `docker system df` once failed on a changing dpkg temporary file. `df -h` recorded actual remaining space; this was not treated as an image-build failure.
- Full official robot bringup reached the initial 512-process/thread limit, causing `Resource temporarily unavailable`. The stationary test switched to the official model description, model spawning, and one sensor-bridge process, raised the limit to 1024, and omitted platform mock, motion, and navigation nodes.
- The reduced launch initially omitted an explicit empty namespace, leaving the control plugin waiting for `/turtlebot4/robot_description`. Passing `namespace:=''` aligned naming and resolved it without modifying installed official packages.
- The official Create 3 URDF includes a Sensors plugin defaulting to ogre. Initial headless runs failed; adding Xvfb and explicitly selecting server-side ogre2 resolved display requirements.
- `xvfb-run` as container PID 1 stalled waiting for readiness. Docker `--init` resolved it. The virtual display was not exposed to the host or network.
- A duplicate Sensors plugin in the test world caused `Scene already exists` and a Gazebo crash. Removing the project's duplicate and using the official URDF plugin resolved it.
- After the first successful image capture, JSON export failed on NumPy `bool_`. Intrinsics and check values were explicitly converted to Python float/bool, then capture was rerun to retain quantitative records.

## Unexecuted at the end of Phase 1 (Phase 2 update below)

Person detection precision/recall, inference FPS, 3D localisation error, IDF1/HOTA during crossings, recovery after target loss, Nav2 following, stopping response, and 30-minute stability were **NOT VERIFIED** at that point. No motion commands were sent and autonomous following was not enabled.

Physical OAK stereo accuracy, VPU performance, IR/low-light behaviour, and physical braking distance are outside this purely virtual test.

## Phase 2: 2D person detection and independent evaluation

PASS: pinned-download verification, five ROS package builds, complete capture/scoring for six scenes, standard vision_msgs output, graph checks for ground-truth isolation, 120 images in a ROS round-trip test without rendering (zero timeouts), a 360-frame HOG comparison, and four scoring unit tests.

Executed entry points and raw records: `scripts/build_perception.sh` → `evidence/phase2/build.log`; `scripts/run_person_case.sh` and `scripts/run_person_suite.sh` → case logs, `frames.json`, and `summary.json`; `scripts/compare_hog_baseline.py` → `hog_baseline.json`; `scripts/run_offline_benchmark.sh` → `offline_roundtrip.json`; `pytest -q tests/test_detection_metrics.py` → `metric_tests.log`.

Across 360 frames and 322 visible person annotations: TP=252, FN=70, FP=0, observed recall=78.26%. Recall was 100% for a nearby single person, 96.67% at a farther distance/different orientation, 68.33% for two crossing people, 40.91% under occlusion, and 89.47% for leaving and re-entering view. These results use one human mesh and simple backgrounds; they do not establish generalisation to real people.

Online reception-path P95 was approximately 53–56ms; sequential ROS round-trip P95 without rendering was approximately 40.15ms. Neither measures full acquisition latency including exposure/early rendering. Details, confidence intervals, HOG window-protocol limitations, screenshots, and failure records are in the [Phase 2 report](phase2_detection.md).

Finding: **the Phase 2 detection baseline is complete, but difficult-scene performance is insufficient for reliable person following**. Tracking, 3D localisation, and navigation were not enabled, and no robot velocity or navigation actions were sent. Only virtual person meshes moved through Gazebo scene services.
