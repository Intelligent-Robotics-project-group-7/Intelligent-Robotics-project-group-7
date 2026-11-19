# TurtleBot 4 Person Detection and Following Research

Project start: 2026-11-10. The virtual setup includes sensor checks, a CPU YOLO baseline, and a Phase 3 prototype that estimates person depth and camera-frame position. The Phase 3 report gives the measured accuracy, coverage, and occlusion results.

The original six-scene benchmark contains 360 frames and 322 visible person annotations. Recall was 78.26% overall, 100% for a nearby single person, 68.33% for crossing people, and 40.91% under occlusion. These are measurements of one synthetic human mesh, not evidence of reliable real-world following. See the [Phase 2 report](docs/phase2_detection.md).

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
git clone --branch robot-CV --single-branch \
  https://github.com/Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7.git robot-cv
cd robot-cv

# One-time host setup; automatically selects the account invoking sudo
sudo bash scripts/bootstrap_host.sh
```

If your account uses SSH authentication, replace the clone URL above with `git@github.com:Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7.git` and keep `--branch robot-CV --single-branch`.

Log out and back in, or disconnect and reconnect SSH, to activate docker-group membership. Return to your clone directory, then confirm Docker access:

```bash
docker info
```

If running the bootstrap from a root shell rather than through your own sudo session, specify an existing non-root account explicitly: `bash scripts/bootstrap_host.sh --user ACCOUNT`. There is no fixed username, UID, or host project path.

Build the simulation image, download and checksum the model/assets, and compile the perception overlay:

```bash
bash scripts/install.sh
```

This runs `build_env.sh` followed by `setup_perception.sh`. The model is approximately 10MB, the person asset approximately 1MB, and additional source/vendor dependencies are downloaded during compilation. The base image and apt packages account for most network and disk usage. Logs remain visible in the terminal; a successful install prints `Installation complete`.

The base image is pinned by digest in [Dockerfile](Dockerfile). Model/asset hashes and the yolo_ros source commit are pinned in [the input lock](config/phase2_assets.lock.json). ONNX Runtime is fixed to CPU version 1.20.0. The upstream CMake build fetches its vendor dependencies online, including huggingface-hub-cpp tag 1.1.5; the resolved commit is recorded in the generated provenance. apt repositories and upstream tags are not historical snapshots, so a later rebuild is not guaranteed to be byte-identical.

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

## Select a YOLO model

YOLO26n is the default. The model catalogue from `robotcv2` also supports YOLO26s, YOLO26m and YOLOv8n. Download the models you want to run. The download script checks their SHA-256 hashes and reuses verified files.

```bash
bash scripts/setup_person_models.sh yolo26s yolov8n
```

Set `TB4_MODEL` when running the Phase 3 suite. The selected detector feeds the same torso-region estimator, and each capture and evaluation records the model ID.

```bash
TB4_MODEL=yolo26s bash scripts/run_depth_suite.sh two_crossing partial_occlusion
bash scripts/run_env.sh python3 scripts/evaluate_depth_suite.py two_crossing partial_occlusion
```

Capture the whole suite with one model for an aggregate report. The evaluator checks that the selected captures use the same model. Use separate checkouts to keep results for multiple models, since a new capture replaces the files for that case.

When launching the simulation manually, set `model:=yolo26s` on `person_detection_eval.launch.py`. For an existing RGB source, run `bash scripts/run_person_detector.sh yolo26s` inside the container and start `person_detection_adapter.py` in the same ROS graph. Model selection takes effect when the detector starts. Wenhao Fan's report includes the original four-model results and screenshots from his local preview. [Model comparison report](docs/robotcv2_model_comparison.md)

## Run Phase 3 person depth evaluation

After installing the Phase 1–2 environment, capture the three plane cases and eleven person/empty cases. Score the captured estimates against the independent simulator geometry.

```bash
bash scripts/run_depth_suite.sh
bash scripts/run_env.sh python3 scripts/evaluate_depth_suite.py
bash scripts/run_env.sh python3 -m pytest -q tests
```

The estimator publishes `/perception/people/depth_estimates` with forward depth, straight-line camera range, optical-frame XYZ, and validity per detection. Captures and per-case simulation logs go under `downloads/phase3/`. The analysis regenerates `evidence/phase3/depth_report.json` and `evidence/phase3/measurements.jsonl`. See the [Phase 3 validation report](docs/phase3_depth.md).

## Run Phase 4 person tracking

After installing the perception stack, run the tracking scenarios and score the recorded tracks against the simulator labels.

```bash
bash scripts/setup_person_models.sh yolo26s
TB4_MODEL=yolo26s bash scripts/run_tracking_suite.sh
bash scripts/run_env.sh python3 scripts/score_tracking.py
```

The measurements go under `downloads/phase4/`. Each test sends one explicit initial selection through the same ROS interface an operator uses. The simulator keeps the robot stationary.

In a running simulation, start the evaluation launch with `phase:=3 tracking:=true`. Read the session ID and a confirmed track ID from `/perception/people/tracks`. Publish a `std_msgs/msg/String` with JSON `{"session_id":"<session>","track_id":1}` to `/perception/people/select_target` within the same ROS graph. To clear the target, send the session ID with `"track_id":null`. After a target reaches `LOST`, send a new explicit selection to resume. The output carries the input image timestamp, confirmed and tentative tracks, and the selected target state. [Phase 4 validation report](docs/phase4_tracking.md)

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

- [Phase 3 depth accuracy, output coverage, and occlusion evaluation](docs/phase3_depth.md)
- [Phase 4 tracking and target lock evaluation](docs/phase4_tracking.md)
- [Four-model detection comparison from robotcv2](docs/robotcv2_model_comparison.md)
- [Clean installation validation](docs/installation_validation.md)
- [Phase 2 detection results, limitations, and reproduction](docs/phase2_detection.md)
- [Industry research and nine open-source projects](docs/industry_research.md)
- [Technology comparison and selection](docs/technology_comparison.md)
- [Proposed system architecture](docs/system_architecture.md)
- [Virtual hardware and resource assessment](docs/hardware_assessment.md)
- [Phased implementation plan and proposed acceptance criteria](docs/implementation_plan.md)
- [Original executed checks and test records](docs/test_report.md)

![Person detection examples](evidence/phase2/detection_contact_sheet.png)

The person mesh is OpenRobotics Scrubs (CC BY 4.0). Attribution is in the Phase 2 report.
