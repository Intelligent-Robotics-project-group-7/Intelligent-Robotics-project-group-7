# Rescue Car v1 — Sensor Interfaces and User Guide

This guide is for Group 7 collaborators using the shared `rescue_robot` simulation. The platform runs on Ubuntu 24.04 with ROS 2 Jazzy and Gazebo Harmonic. The topics and message types below follow `config/bridge_rescue.yaml`, and the startup instructions follow `launch/rescue_platform.launch.py`.

| Team or task | Interfaces to connect first | Integration check |
|---|---|---|
| SLAM and mapping | `/scan`, `/clock`, and `odom → base_link → laser_frame`. Custom algorithms can subscribe to `/odom` or `/imu/data` as needed | Scan points line up with walls, and the mapper publishes `/map` and `map → odom` |
| RGB detection | `/camera/image_raw` and `/camera/camera_info` | Decode the left colour image and timestamp detections with the observation time |
| Stereo ranging | `image_raw` and `camera_info` under `/stereo/left` and `/stereo/right` | Pair left and right frames by timestamp and record the measurement error for a target at a known distance |
| Base control and navigation | Publish `/cmd_vel` and read `/odom` and `/scan` | The robot moves and stops in Gazebo, and its pose and TF update as it moves |

### Interface baseline

The interface table follows the format of the official TurtleBot4 Jazzy simulation bridge. It lists the native Gazebo topic, ROS topic, message types and bridge direction separately. Group code uses the ROS-side interface. The official TurtleBot4 simulator bridge provides RGB, depth images and point clouds. This project computes disparity from two raw images and their calibration. The rescue car accepts `Twist` on `/cmd_vel`. The official TurtleBot4 Jazzy Nav2 configuration enables stamped velocity commands. [Official TurtleBot4 bridge](https://github.com/turtlebot/turtlebot4_simulator/blob/jazzy/turtlebot4_gz_bringup/launch/ros_gz_bridge.launch.py) · [TurtleBot4 Jazzy navigation configuration](https://github.com/turtlebot/turtlebot4/blob/jazzy/turtlebot4_navigation/config/nav2.yaml)

Once the team agrees on v1, keep the public ROS topic names, types, units, time base and frame conventions consistent when changing models. Use the bridge to adapt internal Gazebo paths. Wheel separation, camera intrinsics, sensor mounts, frame rates, noise and the robot footprint are model parameters. Update the SDF, calibration, TF and related settings together when those parameters change. Subscriber code should read the actual values from messages and TF.

## 1. Start the platform

On Ubuntu, open a terminal in the **root of the `learning_pkg_python` package**, where `package.xml`, `launch/`, `config/` and `models/` are located. In Terminal A, run the following.

```bash
source /opt/ros/jazzy/setup.bash
robot_pkg="$(pwd -P)"
ros2 launch "$robot_pkg/launch/rescue_platform.launch.py"
```

Launching the source file by absolute path lets each collaborator keep the repository in their preferred location. Install Gazebo Harmonic, ROS 2 Jazzy, `ros_gz_bridge`, `rviz2` and `tf2_ros`, and make sure `rclpy`, `geometry_msgs`, `nav_msgs` and `sensor_msgs` are available. For ROS and Gazebo setup, see the [Gazebo Harmonic installation guide](https://gazebosim.org/docs/harmonic/ros_installation/).

| Component | File or output used by the current launch |
|---|---|
| Gazebo | `worlds/navigation_test.sdf`, with world name `car_world`, loads `models/rescue_robot/car.sdf` |
| Gazebo–ROS bridge | `config/bridge_rescue.yaml`, node `/bridge_rescue` |
| Noisy wheel odometry | `learning_pkg_python/noisy_odom_node.py` reads `config/odom_noise_rescue.yaml` and runs as `/wheel_noise` |
| Static TF | The launch publishes fixed mounting transforms for the lidar, IMU and both cameras |
| RViz | `config/robot_view.rviz`, using simulation time, `odom` as the default Fixed Frame, and `/scan` configured |

Keep Terminal A running. Source the ROS environment in a separate terminal before starting subscribers, SLAM or stereo processing. The platform supplies sensors and odometry. The corresponding team nodes publish maps and detections.

Run these checks one at a time in Terminal B. Each command exits after receiving a message. If one keeps waiting, press `Ctrl+C` and check Section 8.

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic echo /clock --once
ros2 topic echo /scan --field header --once --qos-reliability best_effort
ros2 topic echo /odom --field child_frame_id --once
ros2 topic echo /camera/image_raw --field header --once --qos-reliability best_effort
```

Expect `laser_frame` as the `/scan` `frame_id`, `base_link` as the `/odom` `child_frame_id`, and `left_camera_optical_frame` as the RGB image `frame_id`. In RViz, the lidar points should lie on the walls and obstacles in the scene.

## 2. Topics and message types

**Use the ROS topics in this table when writing ROS nodes.** `GZ` means Gazebo Transport, and `<robot>` stands for `/model/rescue_robot`. The table lists all 12 bridge mappings. Sections 3 and 4 cover nominal sensor rates and message fields. [ROS–Gazebo bridge configuration](https://github.com/gazebosim/ros_gz/tree/jazzy/ros_gz_bridge)

| ROS topic | ROS message type | Direction | Gazebo topic | Gazebo message type |
|---|---|---|---|---|
| `/cmd_vel` | `geometry_msgs/msg/Twist` | ROS → GZ | `<robot>/cmd_vel` | `gz.msgs.Twist` |
| `/clock` | `rosgraph_msgs/msg/Clock` | GZ → ROS | `/world/car_world/clock` | `gz.msgs.Clock` |
| `/scan` | `sensor_msgs/msg/LaserScan` | GZ → ROS | `<robot>/scan` | `gz.msgs.LaserScan` |
| `/imu/data` | `sensor_msgs/msg/Imu` | GZ → ROS | `<robot>/imu` | `gz.msgs.IMU` |
| `/wheel/odometry_raw` | `nav_msgs/msg/Odometry` | GZ → ROS | `<robot>/odometry` | `gz.msgs.Odometry` |
| `/ground_truth/odom` | `nav_msgs/msg/Odometry` | GZ → ROS | `<robot>/ground_truth/odometry` | `gz.msgs.Odometry` |
| `/stereo/left/image_raw` | `sensor_msgs/msg/Image` | GZ → ROS | `<robot>/stereo/left/image` | `gz.msgs.Image` |
| `/stereo/left/camera_info` | `sensor_msgs/msg/CameraInfo` | GZ → ROS | `<robot>/stereo/left/camera_info` | `gz.msgs.CameraInfo` |
| `/stereo/right/image_raw` | `sensor_msgs/msg/Image` | GZ → ROS | `<robot>/stereo/right/image` | `gz.msgs.Image` |
| `/stereo/right/camera_info` | `sensor_msgs/msg/CameraInfo` | GZ → ROS | `<robot>/stereo/right/camera_info` | `gz.msgs.CameraInfo` |
| `/camera/image_raw` | `sensor_msgs/msg/Image` | GZ → ROS | `<robot>/stereo/left/image` | `gz.msgs.Image` |
| `/camera/camera_info` | `sensor_msgs/msg/CameraInfo` | GZ → ROS | `<robot>/stereo/left/camera_info` | `gz.msgs.CameraInfo` |

ROS nodes provide the following additional interfaces. Each team starts SLAM, stereo processing or detection separately according to its task.

| ROS topic | Type | Publisher and usage |
|---|---|---|
| `/odom`, `/wheel/odometry` | `nav_msgs/msg/Odometry` | `/wheel_noise` publishes the same integrated noisy estimate on both topics. Use `/odom` and the corresponding TF for navigation and mapping |
| `/tf`, `/tf_static` | `tf2_msgs/msg/TFMessage` | `/wheel_noise` publishes `odom → base_link`, and the launch publishes the fixed sensor TF. The active SLAM or localisation node provides `map → odom` |
| `/map` | `nav_msgs/msg/OccupancyGrid` | Published by SLAM or the fixed-map server |
| `/stereo/disparity` | `stereo_msgs/msg/DisparityImage` | Check this output after starting the stereo processing example in Section 4 |
| Proposed `/rescue_target` | `geometry_msgs/msg/PointStamped` | Pending team agreement. The vision node passes a valid target point with its observation timestamp and coordinate frame |

### Time, frames and QoS

1. **Time.** Sensor acquisition time is in `header.stamp.sec` and `header.stamp.nanosec`. Align streams by their acquisition timestamps. To express the timestamp in seconds, use `sec + nanosec × 10⁻⁹`. Set `use_sim_time:=true` on SLAM, RViz and custom nodes that query TF so they share the Gazebo `/clock` time base.
2. **Frames.** Read `header.frame_id` to identify the frame of the data. In `base_link`, x points forward, y left and z up. In a camera optical frame, x points right, y down and z forward. Use TF to account for mounting offsets and query the transform at the message's acquisition time.
3. **QoS.** Start with `qos_profile_sensor_data` for sensor subscriptions. If a topic is listed but no messages arrive, use `ros2 topic info /topic_name -v` to inspect its publishers and QoS. An image header confirms receipt of one frame. Measure continuous delivery and stereo pairing separately. [ROS 2 QoS compatibility](https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html)

## 3. SLAM and mapping team

### 3.1 2D lidar on `/scan`

The configuration specifies a 360° horizontal scan, 360 samples, 10 Hz, a range of `0.08–12.0 m`, a range resolution of `0.01 m` and a range-noise standard deviation of `0.01 m`. The lidar is at `(0.03, 0, 0.48) m` relative to `base_link`. An obstacle must intersect the horizontal scan plane, which is approximately `0.48 m` high, for this sensor to detect it.

| `LaserScan` field | How to read and use it |
|---|---|
| `header.stamp`, `header.frame_id` | Scan reference time and `laser_frame`. The message definition assigns the timestamp to the first ray |
| `ranges[i]` | Range of ray `i`, in metres. For point conversion, filter out non-finite values and ranges outside `range_min` and `range_max`. For free-space clearing, follow the mapping algorithm's no-return policy |
| `angle_min`, `angle_max`, `angle_increment` | Start angle, end angle and angular increment, in radians. Use the actual values in the message. Zero points along positive x and positive angles turn counterclockwise about positive z |
| `scan_time`, `time_increment` | Time between scans and between rays within a scan, in seconds. Read the actual values before applying motion compensation |
| `intensities` | Return intensity, which depends on the sensor implementation and may be empty |

For ray `i`, calculate `θ = angle_min + i × angle_increment`, then `x = ranges[i] × cos(θ)` and `y = ranges[i] × sin(θ)`. The result is a point in `laser_frame`. Apply `odom ← laser_frame` or `map ← laser_frame` at the scan time to overlay the point in the corresponding frame. [LaserScan message definition](https://github.com/ros2/common_interfaces/blob/jazzy/sensor_msgs/msg/LaserScan.msg)

```bash
ros2 topic echo /scan --once --qos-reliability best_effort
ros2 run tf2_ros tf2_echo odom laser_frame --ros-args -p use_sim_time:=true
```

### 3.2 Odometry and IMU

**Noisy wheel odometry.** `/wheel_noise` uses raw wheel velocity and the original message timestamps to integrate a planar pose. It publishes `/odom` and `odom → base_link`. The configured linear-velocity noise standard deviation is `0.01 m/s`, the yaw-rate noise standard deviation is `0.02 rad/s`, the biases are zero, and the random seed is `42`.

| `Odometry` field | Meaning |
|---|---|
| `header.frame_id`, `child_frame_id` | `odom` and `base_link`, respectively, on `/odom` |
| `pose.pose.position`, `pose.pose.orientation` | Position in metres and orientation as a quaternion, expressed in `header.frame_id` |
| `twist.twist.linear`, `twist.twist.angular` | Linear velocity in m/s and angular velocity in rad/s, expressed in `child_frame_id`. For this differential-drive base, focus on `linear.x` and `angular.z` |
| `pose.covariance`, `twist.covariance` | 6×6 covariance matrices flattened in row-major order. The coordinate order is `x, y, z, roll, pitch, yaw`, and the diagonal indices are `0, 7, 14, 21, 28, 35` |

Subscribe to `/ground_truth/odom` for offline error evaluation. Align timestamps and coordinate origins before comparing ground truth with estimates. For online mapping or localisation, use `/odom` or the wheel-motion source agreed for the algorithm. [Odometry message definition](https://github.com/ros2/common_interfaces/blob/jazzy/nav_msgs/msg/Odometry.msg)

**IMU.** `/imu/data` runs at a nominal `50 Hz`. The mount position is `(0, 0, 0.10) m`. The model adds Gaussian noise with standard deviation `0.01 rad/s` to the z-axis angular velocity. `orientation` is a quaternion. `angular_velocity.{x,y,z}` is in rad/s and `linear_acceleration.{x,y,z}` is in m/s². Each `*_covariance` field is a 3×3 matrix. All zeros indicate unknown covariance, and `-1` in the first entry indicates that the corresponding measurement is unavailable. Before fusion, check the measured acceleration direction, gravity and covariance with the robot stationary. The current noisy odometry uses wheel velocity, and the team can connect the IMU to its estimator as needed. [Imu message definition](https://github.com/ros2/common_interfaces/blob/jazzy/sensor_msgs/msg/Imu.msg)

```bash
ros2 topic echo /odom --once
ros2 topic echo /imu/data --once --qos-reliability best_effort
```

### 3.3 Connect SLAM

If using SLAM Toolbox, check these entries in the existing `slam_toolbox.ros__parameters` block in your team configuration, especially `base_frame: base_link`. Keep the other solver parameters from your chosen template. SLAM Toolbox uses TF to obtain the odometry pose at each scan time. A custom algorithm can also subscribe directly to `/odom` to read its message fields. [SLAM Toolbox Jazzy parameter template](https://github.com/SteveMacenski/slam_toolbox/blob/jazzy/config/mapper_params_online_async.yaml)

```yaml
slam_toolbox:
  ros__parameters:
    # ZH: 与救援车的时钟、雷达话题和坐标系匹配。
    # EN: Match the rescue robot's clock, scan topic and frames.
    use_sim_time: true
    mode: mapping
    scan_topic: /scan
    map_frame: map
    odom_frame: odom
    base_frame: base_link
```

During mapping, SLAM publishes `/map` (`nav_msgs/msg/OccupancyGrid`) and `map → odom`. Assign one publisher of `map → odom` per operating mode. Set the RViz Fixed Frame to `map`, add a display for `/map`, and keep `/scan` visible to check that scan points line up with mapped walls. Give the navigation team the scene name, map YAML and image, map frame and initial pose convention.

To use SLAM Toolbox, open another terminal in the package root. If the team needs a configuration file, copy the defaults from the installed `slam_toolbox` package and edit the fields above. The commands below create the team file `slam_rescue.yaml` if it is absent.

```bash
source /opt/ros/jazzy/setup.bash
robot_pkg="$(pwd -P)"
slam_share="$(ros2 pkg prefix --share slam_toolbox)"
slam_config="$robot_pkg/config/slam_rescue.yaml"
if [ ! -e "$slam_config" ]; then
  cp "$slam_share/config/mapper_params_online_async.yaml" "$slam_config"
fi
```

After saving the configuration, start mapping from the same terminal. Once a map appears, drive slowly and watch it expand. [SLAM Toolbox Jazzy launch file](https://github.com/SteveMacenski/slam_toolbox/blob/jazzy/launch/online_async_launch.py)

```bash
ros2 launch slam_toolbox online_async_launch.py \
  slam_params_file:="$slam_config" use_sim_time:=true
```

## 4. RGB detection and stereo ranging team

### 4.1 Select image and calibration topics

- **For RGB detection**, subscribe to `/camera/image_raw` and `/camera/camera_info`. They come from the same camera as the left stereo stream. Pick one set of left-camera topics to avoid duplicate subscriptions in the application.
- **For stereo ranging**, subscribe to each `/stereo/.../image_raw` and its corresponding `camera_info`. Pair the left and right images and calibration by acquisition time, then compute disparity from rectified images.
- **To view images**, install `rqt_image_view`, run `ros2 run rqt_image_view rqt_image_view` and select the left or right topic from the dropdown. To inspect a message in the terminal, print a field such as `encoding` or `header` to keep the output readable.

```bash
ros2 topic echo /camera/image_raw --field encoding --once --qos-reliability best_effort
ros2 topic echo /stereo/left/camera_info --once --qos-reliability best_effort
ros2 topic echo /stereo/right/camera_info --once --qos-reliability best_effort
```

### 4.2 Read `Image` and `CameraInfo`

| Message | Field | Meaning |
|---|---|---|
| `Image` | `width`, `height` | Width and height in pixels. The current configuration is `640 × 480` |
| `Image` | `encoding`, `step`, `is_bigendian`, `data` | Pixel encoding, bytes per row, byte order and image data. The SDF configures `R8G8B8`. Use the encoding in the received ROS message |
| `Image` / `CameraInfo` | `header` | Acquisition time and camera optical frame. Pair the image with calibration from the same camera |
| `CameraInfo` | `distortion_model`, `d` | Distortion model and coefficients |
| `CameraInfo` | `k` | 3×3 intrinsic matrix for the raw image, in row-major order. `k[0] = fx`, `k[4] = fy`, `k[2] = cx`, `k[5] = cy` |
| `CameraInfo` | `r`, `p` | 3×3 rectification rotation and 3×4 rectified-image projection matrix, both in row-major order. For back-projection from the rectified image, use `p[0]`, `p[5]`, `p[2]` and `p[6]` for focal lengths and principal point |

In Python, access these arrays by lowercase field names such as `msg.k` and `msg.p`. With `cv_bridge` installed, `CvBridge().imgmsg_to_cv2(msg, desired_encoding="bgr8")` converts an image for OpenCV using the message's encoding and row stride. [Image message definition](https://github.com/ros2/common_interfaces/blob/jazzy/sensor_msgs/msg/Image.msg) · [CameraInfo message definition](https://github.com/ros2/common_interfaces/blob/jazzy/sensor_msgs/msg/CameraInfo.msg)

Each eye runs at `10 Hz` with a `90°` horizontal field of view and clipping distances of `0.05–15.0 m`. The left and right optical centres are at `(0.421, +0.06, 0.32)` and `(0.421, −0.06, 0.32)` m relative to `base_link`. The baseline is `B = 0.12 m`. The SDF specifies `fx = fy = 320 px`, `cx = 320 px`, `cy = 240 px`, left `p[3] = 0` and right `p[3] = −38.4`. Use the received `CameraInfo` and check the baseline from the right camera with `B = −p[3] / p[0]`. Verify the rendering clip limits and the disparity algorithm's usable range separately.

### 4.3 Measure distance to a detected target

1. **Pair the messages.** Record or subscribe to both images and their calibration and check pairing by `header.stamp`. Separate `echo --once` calls establish that each interface has data. With `stereo_image_proc` and `image_proc` installed, use the command below to start rectification and disparity processing with exact synchronisation. [Jazzy stereo processing launch](https://github.com/ros-perception/image_pipeline/blob/jazzy/stereo_image_proc/launch/stereo_image_proc.launch.py)
2. **Use a common pixel grid.** Run detection on `/stereo/left/image_rect_color` and read the corresponding pixels from `/stereo/disparity`. If the detector uses a resized or raw image, map the bounding box into the rectified left-image coordinates first.
3. **Calculate depth from valid disparity.** In the intersection of the detection region and `valid_window`, use finite, positive disparity `d` within the search range. Calculate `Z = f × T / d` for each pixel, using `f` and `T` from `stereo_msgs/msg/DisparityImage`. The median of valid depths can reduce the effect of background pixels and outliers. Mark the measurement as invalid if too few valid samples are available. [DisparityImage message definition](https://github.com/ros2/common_interfaces/blob/jazzy/stereo_msgs/msg/DisparityImage.msg)
4. **State the frame and distance definition.** `Z` is forward depth along the optical axis. For a valid pixel `(u,v)`, use the left rectified projection parameters to calculate `X=(u−cx)Z/fx` and `Y=(v−cy)Z/fy`. The straight-line distance to the optical centre is `sqrt(X²+Y²+Z²)`. Express the 3D point in `left_camera_optical_frame`, then use TF at the observation time to transform it to `base_link` or to `map` when localisation is available. For handoff to the mission node, the team can agree on a timestamped `geometry_msgs/msg/PointStamped`.

```bash
ros2 launch stereo_image_proc stereo_image_proc.launch.py \
  namespace:=stereo left_namespace:=left right_namespace:=right \
  launch_image_proc:=True approximate_sync:=False
```

In another terminal, run `ros2 topic echo /stereo/disparity --field header --once --qos-reliability best_effort`. Keep the robot stationary and place a textured target directly in front of the left optical centre. With the configured calibration, an optical-axis depth of **2.0 m** gives approximately **19.2 px** of disparity. Check against the actual `CameraInfo` and several frames, then test pairing while the robot moves. The platform supplies images and calibration. The processing node above or the team's algorithm supplies disparity.

## 5. Read data with Python

Save this standalone subscriber as `sensor_probe.py`. It prints a summary of the first message received on each topic. Copy the relevant field reads from `show` into your own callbacks. The sensor subscriptions use `qos_profile_sensor_data`, and the odometry and ground-truth subscriptions use a standard queue.

```python
import math
from functools import partial

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image, Imu, LaserScan


class SensorProbe(Node):
    def __init__(self):
        super().__init__("rescue_sensor_probe")
        self.seen = set()

        # ZH: 明确为每个话题指定消息类型。
        # EN: Give each subscription its explicit message type.
        sensor_topics = {
            "/scan": LaserScan,
            "/imu/data": Imu,
            "/camera/image_raw": Image,
            "/camera/camera_info": CameraInfo,
            "/stereo/left/image_raw": Image,
            "/stereo/left/camera_info": CameraInfo,
            "/stereo/right/image_raw": Image,
            "/stereo/right/camera_info": CameraInfo,
        }
        for topic, msg_type in sensor_topics.items():
            self.create_subscription(
                msg_type, topic, partial(self.show, topic), qos_profile_sensor_data
            )
        for topic in ("/odom", "/wheel/odometry_raw", "/ground_truth/odom"):
            self.create_subscription(Odometry, topic, partial(self.show, topic), 10)

    def show(self, topic, msg):
        if topic in self.seen:
            return
        self.seen.add(topic)
        stamp = msg.header.stamp
        header = f"{topic} | {msg.header.frame_id} | {stamp.sec}.{stamp.nanosec:09d}"

        # ZH: 只显示关键字段，避免把整张图片和所有测距打印到终端。
        # EN: Print key fields rather than full image buffers or range arrays.
        if isinstance(msg, LaserScan):
            valid = [
                r for r in msg.ranges
                if math.isfinite(r) and msg.range_min <= r <= msg.range_max
            ]
            nearest = f"{min(valid):.3f} m" if valid else "no valid returns"
            detail = f"samples={len(msg.ranges)}, nearest={nearest}"
        elif isinstance(msg, Imu):
            detail = f"wz={msg.angular_velocity.z:.3f} rad/s, az={msg.linear_acceleration.z:.3f} m/s²"
        elif isinstance(msg, CameraInfo):
            detail = f"K.fx={msg.k[0]:.2f}, P.fx={msg.p[0]:.2f}, P[3]={msg.p[3]:.2f}"
        elif isinstance(msg, Image):
            detail = f"{msg.width}x{msg.height}, encoding={msg.encoding}, step={msg.step} B"
        else:
            pose = msg.pose.pose.position
            detail = f"child={msg.child_frame_id}, x={pose.x:.3f} m, y={pose.y:.3f} m"
        self.get_logger().info(f"{header} | {detail}")


def main():
    rclpy.init()
    node = SensorProbe()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
```

Run the following from the directory containing `sensor_probe.py`. Press `Ctrl+C` once the summaries appear.

```bash
source /opt/ros/jazzy/setup.bash
python3 sensor_probe.py --ros-args -p use_sim_time:=true
```

Use `ros2 interface show sensor_msgs/msg/LaserScan` to see the message definition. Substitute `sensor_msgs/msg/Imu`, `sensor_msgs/msg/Image`, `sensor_msgs/msg/CameraInfo` or `nav_msgs/msg/Odometry` to inspect the other interfaces.

## 6. TF tree and robot control

```text
map                              Provided by the active SLAM or localisation node
└─ odom                          map → odom published by localisation
   └─ base_link                  odom → base_link published by /wheel_noise
      ├─ laser_frame             (0.03, 0, 0.48) m
      ├─ imu_link                (0, 0, 0.10) m
      └─ stereo_camera_link      (0.421, 0, 0.32) m
         ├─ left_camera_link     (0, +0.06, 0) m relative to the camera rig
         │  └─ left_camera_optical_frame
         └─ right_camera_link    (0, −0.06, 0) m relative to the camera rig
            └─ right_camera_optical_frame
```

The launch configures the camera optical transforms with roll `−π/2`, pitch `0` and yaw `−π/2`. When running the platform on its own, set the RViz Fixed Frame to `odom`. To check the lidar mount, look up `base_link → laser_frame`. Expect translation `[0.030, 0.000, 0.480]` and zero rotation. `tf2_echo` can show `At time 0.0` for a static transform.

For a short drive test in open space, use the test as the sole control source on `/cmd_vel`. Send 20 forward commands at `0.15 m/s`, then send zero velocity. If you interrupt the test with `Ctrl+C`, run the stop command separately.

```bash
ros2 topic pub --rate 10 --times 20 /cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.15}, angular: {z: 0.0}}'
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.0}, angular: {z: 0.0}}'
```

`linear.x > 0` moves the robot forward and `angular.z > 0` turns it left. Teleoperation, test commands and Nav2 share the velocity input. Stop the previous control source before enabling the next one.

### Fixed-map navigation test

Once the platform checks pass, use `navigation_test.sdf` and `rescue_navigation_test.yaml` for a fixed-map test. Finish the SLAM session so AMCL can take over `map → odom`. The current `nav2_test.yaml` enables NavFn's `use_astar: true`, and the global costmap still uses a `robot_radius` of `1.75 m`. If global planning is too conservative in narrow spaces, check that value against the new robot dimensions and inspect the global costmap in RViz. The final Nav2 output on `/cmd_vel` should use `geometry_msgs/msg/Twist` to match the bridge. [NavFn configuration](https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/planners_plugins/configuring_navfn/) · [Nav2 Jazzy launch file](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_bringup/launch/bringup_launch.py)

Open another terminal in the package root and start the map server, AMCL and Nav2.

```bash
source /opt/ros/jazzy/setup.bash
robot_pkg="$(pwd -P)"
ros2 launch nav2_bringup bringup_launch.py \
  map:="$robot_pkg/maps/rescue_navigation_test.yaml" \
  params_file:="$robot_pkg/config/nav2_test.yaml" \
  slam:=False use_composition:=False use_sim_time:=true autostart:=true
```

To select a goal in RViz, run `ros2 launch nav2_bringup rviz_launch.py use_sim_time:=true` in another terminal to open the configuration with Nav2 tools. Set Fixed Frame to `map`. If localisation needs an initial pose, use **2D Pose Estimate** to set the robot's actual position and heading. Once navigation is active, use **Nav2 Goal** to send the robot to a free point about 1 m ahead. Verify that RViz displays a path, the robot moves in Gazebo, and the goal succeeds.

## 7. Record data for integration tests

The mapping team should record scans, odometry, transforms and the simulation clock. Add `/map` once mapping is running and add ground truth for error evaluation as needed.

```bash
ros2 bag record -o rescue_mapping_run /clock /tf /tf_static /scan /odom
```

The vision team should record both image streams and their calibration together. To diagnose timing or ranging issues, compare paired `header.stamp` values and record the fraction of invalid disparity samples.

```bash
ros2 bag record -o rescue_stereo_run /clock /tf /tf_static \
  /stereo/left/image_raw /stereo/left/camera_info \
  /stereo/right/image_raw /stereo/right/camera_info
```

When sharing results, include the scene file, starting pose and launch command. For visual ranging, state whether the value is optical-axis depth or straight-line distance and specify the target point's frame.

## 8. Troubleshooting

| Symptom | First checks |
|---|---|
| Gazebo cannot find `model://rescue_robot` | Confirm `model.config` points to `car.sdf` and start the platform with this package's launch. For a manual Gazebo run, add the parent `models` directory to `GZ_SIM_RESOURCE_PATH` |
| Gazebo shows the robot, but a ROS topic keeps waiting | Check that the simulation is playing. Use `gz topic -l` to inspect native Gazebo topics, then check `bridge_rescue.yaml` and the ROS domain. The world name should match the clock bridge's `car_world` |
| No data on `/odom` | Check the node with `ros2 node info /wheel_noise`, then run `ros2 topic echo /wheel/odometry_raw --field header --once` to verify that raw odometry reaches ROS |
| RViz receives scans but reports a TF error | Use `odom` for platform-only testing. Check `base_link → laser_frame`, `odom → base_link` and `use_sim_time` on the relevant nodes |
| Images arrive with lost-message reports | Use an image viewer or a simultaneous bag recording to check continuous delivery and left–right pairing, then investigate transport, QoS or simulation load |
| Both image streams arrive, but there is no target depth | Check the rectified images, both calibrations, disparity output, timestamp pairing and valid disparity range |

Previous integration logs showed messages on `/clock`, `/wheel/odometry_raw`, `/odom`, `/scan`, the IMU, both image streams, both `CameraInfo` streams and the RGB aliases. The measured `base_link → laser_frame` transform was `[0.030, 0.000, 0.480]` m with zero rotation. After changing the model or sensors, repeat the message checks in Section 1, then follow the relevant team sections to verify scan alignment, image continuity, disparity accuracy and motion control.
