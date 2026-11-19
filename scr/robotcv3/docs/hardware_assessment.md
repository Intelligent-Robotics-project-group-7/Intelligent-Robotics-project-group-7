# Virtual Hardware and Compute Resource Assessment

Date: 2026-11-10. The user has explicitly specified that all hardware is virtual.

## Read-only inspection

SSH: `john@192.168.48.135`; hostname: `john-VMware-Virtual-Platform`.

| Item | Observed result | Engineering implication |
|---|---|---|
| System | Ubuntu 26.04.1 LTS, x86_64, VMware | Use an Ubuntu 24.04 container for the official Jazzy combination |
| CPU | 8 vCPUs, exposed model i7-13650HX | CPU inference and software rendering are possible; this does not guarantee dedicated physical-core performance |
| RAM | Approximately 7.2 GiB; initially 5.2 GiB available; 4 GiB swap | Initial simulation limits: 4 GiB/4 CPUs, leaving resources for the host and existing services |
| Disk | 30G root disk, initially approximately 15G free | Install one environment; avoid large training datasets and multiple GPU frameworks |
| Graphics | VMware SVGA II; /dev/dri present | Does not establish CUDA passthrough; start with Mesa software rendering |
| USB | VMware mouse/hubs and root hub | No visible OAK-D; physical camera model, calibration, and USB rate NOT VERIFIED |
| ROS/source | Initially no /opt/ros, ros2, Docker, or TurtleBot workspace | Create an isolated research directory without changing other projects |
| Physical base/lidar | Not applicable; virtual hardware project | No claim of testing Create 3 firmware or physical RPLIDAR capabilities |

Commands and installation results are recorded in `test_report.md` and evidence. Gazebo camera/lidar models are selected simulation configurations, not physically inventoried devices.

## Compute architecture comparison

| Option | Performance and latency | Power/cooling, USB/network | Drivers/complexity | Cost and current decision |
|---|---|---|---|---|
| A: original OAK inference + Pi running ROS | Inference can be offloaded to the VPU; full-path FPS/depth accuracy NOT VERIFIED | Physical USB3, power, and cooling require checks; detections consume less bandwidth than full RGB-D | RVC/DepthAI/ROS versions must match | Reuse existing hardware if available; no physical device here, so this option cannot be tested |
| B: external Ubuntu computer | CPU/GPU options; network, queues, and codecs add latency | RGB-D transfer requires bandwidth and clock-synchronisation budgets | Keep robot drivers local and connect host perception through standard interfaces | Current VM simulates this division of work; additional software licence cost is 0; no hardware purchase required |
| C: Jetson edge compute | Potential GPU acceleration for supported models; TOPS does not directly translate into FPS | Power conversion, cooling, load, and mounting require measurement | JetPack/ROS/Isaac versions are closely coupled | No purchase recommended now; the official 2024 launch price of $249 is historical, and a 2026 local tax-inclusive total is NOT VERIFIED |
| D: replace/add sensors | A wider field of view may reduce loss from view; depth technologies have different failure modes | More USB/network/power demand and extrinsic calibration | More complex synchronisation, fusion, and fault diagnosis | Unnecessary now; specific models/prices NOT VERIFIED; quantify current model bottlenecks first |

Jetson price source: [NVIDIA announcement, 2024-12-17](https://developer.nvidia.com/blog/nvidia-jetson-orin-nano-developer-kit-gets-a-super-boost). This is not a current quotation. Isaac ROS platform constraints are in the [release 4.0 platform documentation](https://nvidia-isaac-ros.github.io/v/release-4.0/repositories_and_packages/isaac_ros_dnn_inference/index.html).

## Transport and real-time budget

Calculated example, **not a measurement**: 640×480 RGB8 at 30Hz carries approximately 27.65MB/s of raw payload; 32FC1 depth at the same size carries approximately 36.86MB/s. The total is approximately 64.51MB/s (516Mb/s), excluding DDS, IP, point clouds, and retransmission overhead. Simulation and processing therefore remain in one container, without additional dense point-cloud publication initially.

Record actual image dimensions, encodings, and rates. Model input may be reduced for CPU inference, but retain the mapping back to original RGB/depth pixels. Resizing or compression must not break CameraInfo correspondence.

## Simulation validation limits

Simulation can test interfaces, TF, synchronisation, depth units, position calculations, target state machines, navigation calls, sensor timeouts, CPU resources, and simulation-time behaviour.

**NOT VERIFIED:** physical OAK stereo distance error, low-light/IR performance, transparent/reflective objects, real exposure motion blur, USB disconnection behaviour, VPU throughput, physical stopping distance, and crowd safety.

No hardware upgrade is needed in Phase 1. If software rendering produces a low real-time factor, first reduce virtual resolution/frame rate and world complexity, or allocate more VM resources. Consider GPU passthrough or a separate Ubuntu host only after identifying a compute bottleneck.

## Phase 2 measurements

The same image was reused to build a CPU perception overlay, without CUDA/PyTorch or new devices. Skeletal Actor plus ground-truth rendering stalled at the first frame, with a texture-memory budget message. The final setup uses the approximately 1MB OpenRobotics Scrubs rigid mesh, with the evaluation camera configured to 5Hz and 320×240. No single Gazebo, driver, or asset factor has been isolated as the cause.

One occlusion-scene snapshot showed approximately 3.76 logical CPUs, 949MiB, and 181 processes/threads. This is neither a peak nor a long-term stability result. Perception and ground-truth rendering approach the 4-CPU container limit, so resources must be reassessed before adding navigation. Detection quality and latency are documented in the [Phase 2 report](phase2_detection.md).
