# TurtleBot 4 Person Detection and Following Research

Phases 1 and 2 provide technical research, an isolated simulation environment, sensor checks, and 2D person detection. Basic box-centre depth ranging is also available, assuming the robot is at (0, 0, 0) with zero heading. All hardware is virtual. Real robot pose, camera mounting offsets, identity tracking and following are not integrated.

The original six-scene benchmark contains 360 frames and 322 visible person annotations. Recall was 78.26% overall, 100% for a nearby single person, 68.33% for crossing people, and 40.91% under occlusion. These are measurements of one synthetic human mesh, not evidence of reliable real-world following. See the [Phase 2 report](docs/phase2_detection.md).

## Integration status

Integration with commit [ece8c84](https://github.com/Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7/commit/ece8c84aa07ab65b9950223d08c630c2b4139b6f) is pending because of unresolved merge conflicts. That commit has not been merged into this branch; this version remains based on [23d4ef3](https://github.com/Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7/commit/23d4ef304fd5c5dd1f9569ccbeaa90554fce6038).

## My work and the model speed/accuracy trade-off

This revision builds on the `robot-CV` YOLO26n baseline at commit [23d4ef3](https://github.com/Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7/commit/23d4ef304fd5c5dd1f9569ccbeaa90554fce6038), adding selectable models and person-centre distance and bearing outputs. The improvement figures in this section refer to that specific baseline version.

I tested YOLO26n, YOLO26s, YOLO26m and YOLOv8n through the same detection pipeline. On the same 360 synthetic frames containing 322 visible person annotations, recall increased from 78.26% with the `23d4ef3` baseline to 95.03% with YOLO26s or YOLO26m; YOLOv8n reached 93.17%. Compared with `23d4ef3`, the added model options improve measured detection coverage and allow a choice between accuracy and processing speed. The larger models required more processing time, and YOLO26s and YOLO26m achieved the same recall, so a larger model did not automatically improve every accuracy measure. These results describe this synthetic benchmark, rather than a demonstrated improvement on physical robots.

For my current accuracy-focused experiments, I have chosen YOLO26m, the largest model in the current set. This helps me investigate detection quality, but it may reduce the rate at which new person positions become available. The robot has a limited computing budget, so the final model choice needs to balance accuracy, processing speed and the resources needed by the rest of the system.

This trade-off matters especially when the person is moving. Even a correctly detected position can already be out of date when processing finishes. If inference or message queues fall behind, position updates may arrive too slowly to describe the person's current location. High accuracy on individual images therefore does not by itself establish good performance for person following.

I have added live FPS and receipt-latency counters to the preview so that I can switch models and observe their behaviour with a moving virtual person. The planning table below uses estimates; a complete four-model sustained live benchmark has not been completed for that table. My next step is to evaluate end-to-end latency, position update rate and observation age on the intended robot hardware. Delayed updates during real following remain a concern to test, rather than a failure already demonstrated on the physical robot.

## My computer and expected live performance

The development computer configuration was read locally on 11 November 2026:

| Component | Configuration |
|---|---|
| Host CPU | Intel Core i9-14900HX, 24 cores / 32 logical processors |
| Installed RAM | 32 GiB, two 16 GiB modules |
| Host GPU | NVIDIA GeForce RTX 4060 Laptop GPU, approximately 8 GiB VRAM (8188 MiB reported) |
| Host OS | Windows 11 Pro, build 26200 |
| Ubuntu VM | 16 logical vCPUs and 15946 MiB visible RAM (about 15.6 GiB) |
| Test container limit | 4 CPUs and 4 GiB RAM, shared by simulation, detection, ranging and preview |
| Model execution | ONNX Runtime CPU, 2 inference threads; no CUDA inference or GPU passthrough |
| Camera configuration | 320x240 RGB/depth, 5 frames per simulated second; software rendering |

The host has an RTX GPU, but this pipeline currently performs inference and simulation rendering on the CPU. These resource limits are part of the current development setup and do not describe the laptop's maximum available performance or the Raspberry Pi/OAK hardware on a physical robot.

### Estimated performance, not full benchmark results

The following are approximate planning ranges informed by earlier CPU replay results and brief/partial live checks. They are **estimates**, not a completed, controlled four-model live benchmark, confidence intervals or guaranteed limits. Actual rates and delays vary with rendering load, virtual-machine scheduling, scene complexity and other work on the computer.

| Model | Estimated detection update rate, wall-clock FPS | Estimated RGB-receipt-to-detection delay |
|---|---:|---:|
| YOLO26n | about 3.5-5 FPS | about 25-60 ms |
| YOLO26s | about 3-4.5 FPS | about 80-160 ms |
| YOLO26m | about 2-3.5 FPS | about 250-600 ms |
| YOLOv8n | about 3.5-5 FPS | about 35-80 ms |

FPS here means expected detection-result updates per real second in this simulated pipeline. It is not maximum model throughput and is not calculated as `1000 / latency_ms`. The configured 5 Hz camera rate uses simulation time; when rendering runs slower than real time, the actual input rate is lower. Rendering and inference also compete for the container's CPU allocation. Similar FPS values can therefore hide quite different per-frame processing delays.

The delay starts when the preview receives the RGB message and ends when it receives the detection for the same source timestamp. It excludes sensor acquisition, rendering and any transport before RGB reaches that subscriber. It is not pure neural-network inference time or a complete camera-to-robot-control latency.

### Interactive performance display

The local preview tools in `treerobot-CVothers` let me click the model buttons or press `1` to `4` to select YOLO26n, YOLO26s, YOLO26m or YOLOv8n. `N` selects the next model; `Q` or Esc closes the preview. Switching reloads the detector and clears old image/result caches before displaying the new model's data.

The screen shows **actual live measurements over a rolling five-second wall-clock window**, separately from the estimates above:

- **RGB FPS:** received RGB messages per second.
- **Detect FPS:** detection-array messages per second, including arrays with no person.
- **Position FPS:** frames per second with at least one valid distance point; it is not a persistent tracked-person rate.
- **View FPS:** new same-frame RGB/depth/detection/distance combinations handed to the preview per second.
- **P50/P95 latency:** same-source-timestamp RGB receipt to detection or distance-result receipt. Invalid callback-order pairs are counted separately and excluded from these latency percentiles.
- **Sample age:** time from RGB receipt to preparing that displayed sample, not the physical display's scan-out delay.

The virtual person moves repeatedly from side to side while the robot remains stationary. This helps make delayed updates visible, but it does not test real walking, identity tracking or autonomous following. Test scripts, raw performance records and preview code remain in `treerobot-CVothers`.

## Supported setup and prerequisites

- An x86_64 Ubuntu 24.04 or 26.04 Linux host/VM, an existing non-root account, and sudo access for host setup. ROS runs inside an Ubuntu 24.04 container. Native Windows/macOS, ARM, and physical cameras are outside the validated setup; on Windows, use an Ubuntu VM.
- Recommended host resources: 8 vCPUs, 8GB RAM, and at least 16GB free disk space before installation. Runtime containers use at most 4 CPUs and 4GiB RAM. Software rendering shares the CPU with inference and may run slower than real time.
- A working local Docker daemon and permission for your normal user to access it. The bootstrap below installs Ubuntu's Docker package if Docker is absent, preserves an existing Docker installation, and adds the selected account to the docker group. Docker-group membership grants administrator-equivalent host access.
- GitHub access to this repository. If HTTPS cloning requests authentication, configure your own Git credentials with repository access, or use the SSH URL with your registered key. Installation scripts do not contain or configure GitHub credentials.
- Internet access during installation to Docker Hub, Ubuntu/ROS apt repositories, GitHub and its release assets, Hugging Face, and Gazebo Fuel. No API keys are required for the public inputs. Runtime evaluation uses `--network none` and downloads nothing.
- Use a local Linux filesystem for the clone, with a writable checkout. Spaces in the directory name are supported; commas are rejected because of Docker bind-mount syntax. Run project scripts as your normal user, not with sudo.

No host ROS, CUDA, PyTorch, GPU, display server, or physical robot is required. Python tools and compilers used for perception run in the container; the bootstrap also installs host Git, Python 3, and CA certificates.

## Install from a fresh clone

Run in an Ubuntu terminal. Choose any clone location; scripts resolve the repository directory automatically.

```bash
# Only needed if Git is not already installed
sudo apt-get update
sudo apt-get install --no-install-recommends -y git ca-certificates

# Clone the requested branch into a directory you own
git clone --branch main --single-branch \
  https://github.com/Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7.git robot-cv
cd robot-cv/scr/robotcv2

# One-time host setup; automatically selects the account invoking sudo
sudo bash scripts/bootstrap_host.sh
```

If your account uses SSH authentication, replace the clone URL above with `git@github.com:Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7.git` and keep `--branch main --single-branch`.

Log out and back in, or disconnect and reconnect SSH, to activate docker-group membership. Return to your clone directory, then confirm Docker access:

```bash
docker info
```

If running the bootstrap from a root shell rather than through your own sudo session, specify an existing non-root account explicitly: `bash scripts/bootstrap_host.sh --user ACCOUNT`. There is no fixed username, UID, or host project path.

Build the simulation image, download and checksum the model/assets, and compile the perception overlay:

```bash
bash scripts/install.sh
```

This runs `build_env.sh` followed by `setup_perception.sh`. Four ONNX detection models total approximately 143MB, the person asset approximately 1MB, and additional source/vendor dependencies are downloaded during compilation. The base image and apt packages account for most network and disk usage. Logs remain visible in the terminal; a successful install prints `Installation complete`.

The base image is pinned by digest in [Dockerfile](Dockerfile). The original Phase 1–2 assets and yolo_ros source commit are recorded in [the input lock](config/phase2_assets.lock.json). Additional model filenames and download URLs are in [config/person_models.json](config/person_models.json). ONNX Runtime is fixed to CPU version 1.20.0. The upstream CMake build fetches its vendor dependencies online, including huggingface-hub-cpp tag 1.1.5; the resolved commit is recorded in the generated provenance. apt repositories and upstream tags are not historical snapshots, so a later rebuild is not guaranteed to be byte-identical.

Large inputs and build products are generated locally in `downloads/` and `research_ws/` and are excluded from Git. Installation does not require any archive, model cache, or compiled workspace from the original server. The committed input lock is preserved; actual downloaded metadata is recorded in `downloads/phase2/assets.actual.json`.

## Verify installation and run Phases 1–2

```bash
bash scripts/verify_install.sh
```

This runs four scoring tests, the 45-second stationary RGB-D/lidar/TF check, all six person-detection scenes, HOG comparison, a 120-image ROS round-trip replay without rendering, and result/provenance generation. Allow several minutes after compilation. It stops at the first failed command and prints `PASS` only after the checks complete.

Inspect the generated results:

- `evidence/sensor_smoke.json`: `pass` must be true; includes received messages and sensor checks.
- `evidence/phase2/detection_report.json`: six scenes, frame counts, precision/recall, and conditional uncertainty. The baseline target is 60 paired frames per scene; simulated rendering can vary between runs.
- `evidence/phase2/offline_roundtrip.json`: replay timeouts must be zero; timing excludes sensor acquisition.
- `evidence/install_check.json`: final pass/fail, runtime UID/GID, case coverage, and image-hash verification summary.
- `evidence/phase2/detection_contact_sheet.png`: green predictions and blue independent ground-truth boxes.
- `evidence/phase2/provenance.json`: actual image, software, asset, and project provenance.

Rerunning tests replaces generated evidence in that checkout. Use a separate clone if you want to retain the committed historical measurements alongside new results. Installation success confirms the sensor/detection pipeline runs; it does not mean crossing/occlusion accuracy is sufficient for following.

Individual commands are also available:

```bash
# Stationary virtual sensor check only
bash scripts/run_env.sh bash scripts/run_smoke.sh

# Rebuild only perception, then run the complete scene suite and analysis
bash scripts/setup_perception.sh
bash scripts/run_person_suite.sh
bash scripts/analyze_person_suite.sh

# Optional interactive shell; the wrapper automatically detects a terminal
bash scripts/run_env.sh bash
```

All runtime wrappers use the caller's numeric UID/GID, a writable temporary home, a dynamically located host checkout, and the constant internal mount `/workspace`. They work without a TTY in SSH/CI. No physical devices are mapped; capabilities are dropped and resources are limited. Scene services move only synthetic person meshes; no robot velocity or navigation goals are sent.

## Select a detection model

Available models are **YOLO26n** (default), **YOLO26s**, **YOLO26m**, and **YOLOv8n**. Their filenames and download URLs are in [config/person_models.json](config/person_models.json). The model helper reuses existing nonempty files and downloads missing models; no model checksum configuration is required. The weights are community ONNX exports with AGPL-3.0 terms.

Existing installations can download the models without rebuilding or installing PyTorch:

```bash
python3 scripts/person_models.py list
bash scripts/setup_person_models.sh
```

For a manually prepared simulation, select the launch model with `model:=yolo26s` (or another registered ID). For an existing RGB topic, inside the ROS container use `bash scripts/run_person_detector.sh yolo26s`; start `person_detection_adapter.py` separately for the standard person-only output. Standalone detector selection does not start a camera, tracking, navigation, or robot motion.

## Person-centre distance and turn angle

`scripts/person_distance.py` reads the depth at the geometric centre of a YOLO person box and calculates the distance and bearing to that point. The detection launch file starts it automatically. This is the centre of the image rectangle, not the person's centre of mass or a fixed anatomical landmark.

For now, the robot is assumed to be at `(0, 0, 0)` with heading `0`. The camera is assumed to share that origin and face horizontally forward. Coordinates use `x` forward, `y` left and `z` up. Odometry, localisation, TF and the real camera mounting offset are not applied. The output frame is named `assumed_robot`; it is not a calibrated `base_link` or map frame.

### Temporary method and possible improvements

**Box-centre ranging is a temporary baseline, not the final target-point selection method.** It gives usable readings for the current upright synthetic person, but body proportions and pose can move the box midpoint away from the torso. A person with long legs, separated legs or an unusual pose may have a box centre that falls on an unsuitable body region, a gap between the legs or the background. Occlusion and a loose detection box can also make the centre pixel measure an obstacle or background surface instead of the intended person.

The detector has produced useful results in the tested scenes, but these use one human mesh and simple backgrounds. They do not establish that the detector or the selected depth point will remain reliable in clutter, crowds, strong occlusion, changing poses or camera motion. A correct person detection does not by itself guarantee a correct 3D target point. In particular, `valid=true` only means that the selected pixel has usable depth; it does not verify that the pixel belongs to the intended body region.

Two possible improvements still need testing:

- **YOLO Pose keypoints and confidence scores.** A pose model could provide a body skeleton and a confidence score for each keypoint. Visible, sufficiently confident shoulder or hip keypoints could help define a torso reference point or a small body region, rather than always using the rectangle midpoint. Keypoint confidence is a model score, not a guarantee of correct anatomy or depth. The selected region would still need checks for occlusion and valid depth; an uncertain or missing keypoint should not be treated as a reliable target.
- **Depth-based shape or contour cues.** Depth discontinuities and nearby surface structure could help select body pixels inside the detected region and reject some background pixels. A depth image does not automatically provide a person-specific silhouette: nearby objects, similar depths, occlusion and missing depth can make the contour ambiguous. Whether these cues improve target selection in complex scenes is currently unknown.

These are proposed directions, not implemented features or demonstrated improvements. The current models publish detection boxes; the current distance node still uses the box centre. The next comparison should evaluate the box-centre baseline, pose-guided points and depth-guided regions on the same data, including different body proportions, long-leg cases, poses, clutter and occlusion. It should measure target-point selection errors, position error, invalid readings, temporal stability and processing time, as well as detection quality. More accurate target points in complex environments remain to be tested.

### Inputs and calculation

The node subscribes to three messages with the same source timestamp:

| Input topic | Purpose |
|---|---|
| `/perception/people/detections2d` | Person-box centre pixel `(u, v)` |
| `/oakd/rgb/preview/depth` | Depth at the centre pixel |
| `/oakd/rgb/preview/camera_info` | Camera intrinsics `fx, fy, cx, cy` |

RGB and depth must be aligned and have matching dimensions. The current implementation requires rectified images. Exact timestamp matching prevents an old box from being combined with a newer depth image. `32FC1` depth is read in metres; `16UC1` depth is read in millimetres and converted to metres. See [ROS REP-118](https://reps.openrobotics.org/rep-0118/) for the depth-unit convention.

The calculation below uses the depth `D` from the nearest integer pixel to the box centre. The floating-point box centre is used to calculate the viewing direction:

```text
u = (left + right) / 2
v = (top + bottom) / 2

x = D
y = -(u - cx) * D / fx
z = -(v - cy) * D / fy

distance_m        = sqrt(x*x + y*y + z*z)
ground_distance_m = sqrt(x*x + y*y)
turn_yaw_rad      = atan2(y, x)
turn_yaw_deg      = turn_yaw_rad * 180 / pi
```

This converts optical coordinates into forward/left/up coordinates, following the axis convention in [ROS REP-103](https://www.ros.org/reps/rep-0103.html). `depth_m` is depth along the camera's forward optical axis. For an off-centre point, it differs from the straight-line distance `distance_m`.

### Output fields

`/perception/people/distances` uses `std_msgs/msg/String` containing JSON. Each entry in `people` describes one detection:

| Field | Meaning |
|---|---|
| `stamp` | Source image timestamp |
| `robot_position_m`, `robot_yaw_rad` | Current placeholder origin and zero heading |
| `detection_index` | Index in this frame's detection list, not a persistent person ID |
| `center_px`, `sample_pixel` | Floating-point box centre and sampled integer depth pixel |
| `valid` | Whether usable depth was obtained at the selected centre pixel |
| `position_m` | `x, y, z` in the assumed robot frame, in metres |
| `distance_m` | 3D straight-line distance from the origin to the sampled surface point, in metres |
| `ground_distance_m` | Distance projected onto the horizontal plane, in metres |
| `turn_yaw_rad`, `turn_yaw_deg` | Left/right bearing towards the point, in radians and degrees |
| `reason` | Reason for an invalid measurement; present when `valid=false` |

Positive turn angles mean left, negative angles mean right and zero means straight ahead. This is the target point's relative bearing, not a measured robot rotation or angular velocity. Real robot position, heading and camera mounting transforms will be added later.

The following is an actual output from a virtual single-person scene, with values rounded:

```json
{
  "robot_position_m": {"x": 0.0, "y": 0.0, "z": 0.0},
  "robot_yaw_rad": 0.0,
  "people": [{
    "detection_index": 0,
    "valid": true,
    "center_px": {"u": 210.44, "v": 81.39},
    "sample_pixel": {"u": 210, "v": 81},
    "depth_m": 3.4798,
    "position_m": {"x": 3.4798, "y": -0.7914, "z": 0.6058},
    "distance_m": 3.6197,
    "ground_distance_m": 3.5686,
    "turn_yaw_rad": -0.2236,
    "turn_yaw_deg": -12.8127
  }]
}
```

The point is ahead and to the right, at a horizontal distance of about 3.57 metres and a rightward bearing of about 12.81 degrees. The single-person run produced 127 valid readings. This verifies the simulated data path, not physical ranging accuracy or reliable anatomical target selection.

`/perception/people/center_poses` provides the same valid points as a standard `geometry_msgs/msg/PoseArray`. Position matches `position_m`. Each quaternion represents the yaw towards the point, not the person's own facing direction.

### Start and read the data

From the Ubuntu project directory, enter the container and run the remaining commands in that same container terminal:

```bash
bash scripts/run_env.sh bash
source /opt/ros/jazzy/setup.bash
source /workspace/research_ws/install/setup.bash
python3 scripts/prepare_person_world.py single_front
xvfb-run -a ros2 launch /workspace/launch/person_detection_eval.launch.py \
  case:=single_front model:=yolov8n > /tmp/person_detection.log 2>&1 &
ros2 topic echo /perception/people/distances
```

Each invocation of `run_env.sh` creates a separate network-isolated container, so start the nodes and read their output in the same container. Press Ctrl+C to stop reading. Exiting the container ends that run.

A ROS Python subscriber can read the values as follows:

```python
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

def receive(msg):
    data = json.loads(msg.data)
    for person in data['people']:
        if person['valid']:
            distance = person['ground_distance_m']
            angle = person['turn_yaw_deg']
            print(f'Ground distance {distance:.2f} m, turn angle {angle:.1f} deg')

rclpy.init()
node = Node('read_person_distance')
subscription = node.create_subscription(String, '/perception/people/distances', receive, 10)
rclpy.spin(node)
```

Check `valid` before reading distance values. Zero, NaN or infinite centre depth, or a centre outside the image, produces an invalid reading without a distance value; failure is not reported as zero metres. A frame without people has `people=[]`. These checks reject unusable measurements but cannot identify every semantically wrong surface point.

If a complete set of same-timestamp inputs is unavailable, the node publishes no new distance. Consumers should check reception time and discard stale data, for example after 0.5 seconds without an update. `stamp` uses simulation time; do not subtract it directly from UTC time to decide whether data is stale. In a multi-person scene, target selection is a separate task: the first array entry is not a permanently locked person.

The current output is for inspecting distance and bearing data. It sends no base velocities or navigation commands, and the temporary centre-point method should not be treated as a finished person-following solution.

## Rebuild and troubleshooting

```bash
# Rebuild without application-layer cache and refresh the pinned base manifest
bash scripts/install.sh --no-cache --pull

# Optional: use a separate image tag for an independent checkout
export TB4_IMAGE=turtlebot4-research:my-test
bash scripts/install.sh
bash scripts/verify_install.sh
```

- **Docker unavailable/permission denied:** finish the host bootstrap, reconnect your session, and retry `docker info` without sudo. If Docker is installed but the daemon is stopped, start it with `sudo systemctl start docker` on a systemd host.
- **Download or registry failure:** check the installation endpoints listed above and retry installation. Asset downloads use temporary files and retries; cached immutable files are checked against committed hashes. A hash mismatch is an error: do not disable verification. Remove only the named corrupt input from your own clone before retrying.
- **Overlay missing:** run `bash scripts/setup_perception.sh` and inspect the compiler output before starting evaluation. All five upstream packages must build successfully.
- **Insufficient disk/memory or slow rendering:** inspect `df -h`, `free -h`, and Docker resource usage, then allocate the recommended VM resources. Do not interpret simulation-time FPS as wall-clock performance. Case-specific logs are in `evidence/phase2/CASE/simulation.log` and `evidence/phase2/CASE_console.log`.
- **Switching directories after compiling:** CMake/colcon outputs may contain absolute paths. Clone/build in the intended location; rebuild the overlay after moving it. Keep the same `TB4_IMAGE` for installation and execution.

## Reports and evidence

- [Clean installation validation](docs/installation_validation.md)
- [Phase 2 detection results, limitations, and reproduction](docs/phase2_detection.md)
- [Industry research and nine open-source projects](docs/industry_research.md)
- [Technology comparison and selection](docs/technology_comparison.md)
- [Proposed system architecture](docs/system_architecture.md)
- [Virtual hardware and resource assessment](docs/hardware_assessment.md)
- [Phased implementation plan and proposed acceptance criteria](docs/implementation_plan.md)
- [Original executed checks and test records](docs/test_report.md)

![Live YOLO preview with model switching, person-centre measurements, FPS and receipt latency](docs/images/live_yolo_performance.png)

YOLOv8n preview with the selected model highlighted and live person-centre measurements.

![YOLO26n preview with RGB and depth, centre point, distance, turn angle, FPS and receipt latency](docs/images/live_yolo26n_performance.png)

YOLO26n baseline preview, showing the same distance and bearing outputs with live performance counters.

![YOLO26m preview with RGB and depth, centre point, distance, turn angle, FPS and receipt latency](docs/images/live_yolo26m_performance.png)

YOLO26m preview, showing the larger model's live update rate and receipt latency in the moving-person scene.

These are actual preview snapshots with rolling five-second measurements, captured at different moments. Their displayed values are separate from the estimated performance ranges above and do not form a controlled same-frame model comparison. The YOLO26n and YOLO26m images were saved during a partial timed run; the full four-model timed comparison was not completed. The original detection contact sheet remains in `evidence/phase2/detection_contact_sheet.png`.

Person mesh: OpenRobotics Scrubs, CC BY 4.0; attribution and limitations are in the Phase 2 report. Physical OAK depth accuracy, VPU performance, calibrated robot-frame localisation, identity tracking, navigation, and autonomous following remain **NOT VERIFIED**.
