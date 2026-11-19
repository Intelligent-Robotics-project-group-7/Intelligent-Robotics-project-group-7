# turtlebot4
Turtlebot4 common packages.

Visit the [TurtleBot 4 User Manual](https://turtlebot.github.io/turtlebot4-user-manual/software/turtlebot4_common.html) for details.

# Group 7 · TurtleBot4 视觉测试 / TurtleBot4 Vision Test

本目录提供 Group 7 的 Gazebo 迷宫 `group7_test` 和三个站立人形，供队友用 TurtleBot4 Standard 的 RGB 相机测试检测算法。

This directory provides the Group 7 Gazebo maze `group7_test` and three standing human actors for testing detection algorithms with the TurtleBot4 Standard RGB camera.

| 文件 / File | 用途 / Purpose |
| --- | --- |
| `group7_test.sdf` | 墙体、障碍物及三个测试目标 / Walls, obstacles, and three test targets |
| `people_assets/stand.dae` | 三个人形共用的本地模型 / Local mesh shared by the three actors |

## 1. 安装 / Install

使用 Ubuntu 24.04、ROS 2 Jazzy 和 Gazebo Harmonic。官方 TurtleBot4 仿真包提供小车模型、充电座及 ROS–Gazebo 桥接。已经安装仿真包的组员可直接跳到第 2 步。

Use Ubuntu 24.04, ROS 2 Jazzy, and Gazebo Harmonic. The upstream TurtleBot4 simulator package provides the robot model, dock, and ROS–Gazebo bridges. If you already have the simulator installed, skip to step 2.

```bash
sudo apt update
sudo apt install ros-jazzy-turtlebot4-simulator ros-jazzy-irobot-create-nodes
source /opt/ros/jazzy/setup.bash
ros2 pkg prefix --share turtlebot4_gz_bringup
```

[官方安装指南，包括 Gazebo Harmonic / Official installation guide, including Gazebo Harmonic](https://turtlebot.github.io/turtlebot4-user-manual/software/turtlebot4_simulator.html#installation)

## 2. 启动场景 / Launch the world

在小组仓库根目录运行以下命令。如果你把场景放在仓库中的其他位置，把第一行换成进入实际场景目录的命令。启动时所在的目录应包含 `group7_test.sdf` 和同级的 `people_assets/`。官方 SLAM、定位、Nav2 和 RViz 在这次启动中关闭。

Run these commands from the team repository root. If you keep the world elsewhere in the repository, change the first line to enter that directory. Launch from the directory containing both `group7_test.sdf` and `people_assets/`. This launch leaves upstream SLAM, localisation, Nav2, and RViz off.

```bash
cd scr/turtlebot4_scene
source /opt/ros/jazzy/setup.bash
LIBGL_ALWAYS_SOFTWARE=1 ros2 launch turtlebot4_gz_bringup turtlebot4_gz.launch.py \
  world:=group7_test model:=standard \
  slam:=false localization:=false nav2:=false rviz:=false
```

`LIBGL_ALWAYS_SOFTWARE=1` 沿用 VMware 下的软件渲染设置。有可用的硬件渲染时，可以省去这个前缀。场景改名时，请同步修改 SDF 内的 `<world name="...">` 和 `world:=...`，以便桥接找到对应世界的传感器话题。

`LIBGL_ALWAYS_SOFTWARE=1` uses software rendering, as in the VMware setup. You can omit the prefix if hardware rendering works on your machine. If you rename the scene, update the SDF's `<world name="...">` and `world:=...` together so the bridges resolve the sensor topics for that world.

[TurtleBot4 Jazzy 仿真启动文件 / TurtleBot4 Jazzy simulation launch](https://github.com/turtlebot/turtlebot4_simulator/blob/jazzy/turtlebot4_gz_bringup/launch/sim.launch.py)

## 3. 验证传感器 / Verify sensor streams

等待小车出现并确认仿真正在播放。在另一个终端读取一帧 RGB 图像的元数据。

Wait for the robot to appear and make sure the simulation is playing. In a second terminal, read the metadata for one RGB frame.

### RGB 图像 / RGB image

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic echo /oakd/rgb/preview/image_raw --once --no-arr --qos-reliability best_effort
```

看到 `header`、`width`、`height` 和 `encoding` 表示 ROS 收到了图像。安装了 `rqt_image_view` 的组员可以运行 `ros2 run rqt_image_view rqt_image_view`，选择同一个话题，检查起点前方约 2 m 的人形是否进入镜头。

Seeing `header`, `width`, `height`, and `encoding` confirms ROS received an image. If `rqt_image_view` is installed, run `ros2 run rqt_image_view rqt_image_view`, select the same topic, and check whether the actor about 2 m ahead of the spawn point is in view.

### 深度图、标定和点云 / Depth image, calibration, and point cloud

```bash
ros2 topic echo /oakd/rgb/preview/depth --once --no-arr --qos-reliability best_effort
ros2 topic echo /oakd/rgb/preview/camera_info --once --qos-reliability best_effort
ros2 topic echo /oakd/rgb/preview/depth/points --field fields --once --qos-reliability best_effort
```

第一条看深度图尺寸、`encoding` 和坐标系。第二条看内参矩阵 `k` 和投影矩阵 `p`。第三条检查点云是否有 `x`、`y`、`z` 字段。测距前按深度图编码读取像素，并用已知距离的物体核对读数。

The first command checks the depth image dimensions, encoding, and frame. The second shows the intrinsic matrix `k` and projection matrix `p`. The third checks for the point cloud's `x`, `y`, and `z` fields. For ranging, decode pixels according to the depth encoding and check the reading against an object at a known distance.

### LiDAR、里程计和仿真时间 / LiDAR, odometry, and simulation clock

```bash
ros2 topic echo /scan --once --no-arr --qos-reliability best_effort
ros2 topic echo /scan --field ranges --once --qos-reliability best_effort
ros2 topic echo /odom --once --no-arr --qos-reliability best_effort
ros2 topic echo /clock --once
```

- `/scan` 先看时间戳、`frame_id` 和量程，再看 `ranges`。对着墙时，量程内的有限数值表示测得的距离，单位是米。 / Check the timestamp, frame, and range limits, then read `ranges`. Finite readings within the limits represent distances in metres.
- `/odom` 看父坐标系 `header.frame_id`、车体坐标系 `child_frame_id`、位姿和速度。小车移动时，重新读取一帧，检查位置或朝向是否变化。 / Check the parent and child frames, pose, and velocity. Read another sample after moving the robot and look for a change in position or heading.
- `/clock` 在仿真播放时应持续前进。想看连续输出，可去掉 `--once`，用 Ctrl+C 退出。 / The clock should advance while the simulation runs. Omit `--once` to watch it continuously and press Ctrl+C to exit.

### 底盘红外、轮速和可选 IMU / Base IR, wheel speeds, and optional IMU

```bash
ros2 topic list -t
ros2 topic echo /ir_intensity --once --qos-reliability best_effort
ros2 topic echo /wheel_vels --once --qos-reliability best_effort
ros2 topic list -t | grep 'sensor_msgs/msg/Imu'
```

`/ir_intensity` 用于检查红外传感器读数。对比小车静止和运动时的 `/wheel_vels`。IMU 以最后一条命令显示的实际话题为准。如果列出 IMU 话题，执行 `ros2 topic echo <实际话题名> --once --qos-reliability best_effort`，查看 `angular_velocity` 和 `linear_acceleration`。如果 ROS 侧没有列出 IMU，可用 `gz topic -l | grep -i imu` 检查 Gazebo 侧。

Use `/ir_intensity` to check IR readings and compare `/wheel_vels` while stopped and moving. For IMU, use the topic reported by the last command. If an IMU topic appears, run `ros2 topic echo <actual-topic-name> --once --qos-reliability best_effort` and check `angular_velocity` and `linear_acceleration`. If ROS lists no IMU topic, check Gazebo with `gz topic -l | grep -i imu`.

如果某个 `echo` 持续等待，按 Ctrl+C，再用 `ros2 topic info /scan -v --no-daemon --spin-time 3` 检查发布者。把 `/scan` 换成正在排查的话题。如果使用了 ROS 命名空间，按 `ros2 topic list -t` 显示的完整名称订阅。

If an `echo` command keeps waiting, press Ctrl+C and run `ros2 topic info /scan -v --no-daemon --spin-time 3` to check the publisher. Replace `/scan` with the topic you are investigating. If you use a ROS namespace, subscribe to the full name shown by `ros2 topic list -t`.

| ROS 话题 / ROS topic | 消息类型 / Message type | 用途 / Use |
| --- | --- | --- |
| `/oakd/rgb/preview/image_raw` | `sensor_msgs/msg/Image` | RGB 目标检测 / RGB target detection |
| `/oakd/rgb/preview/depth` | `sensor_msgs/msg/Image` | 可选深度测距，先检查 `encoding` / Optional depth ranging; check `encoding` first |
| `/oakd/rgb/preview/camera_info` | `sensor_msgs/msg/CameraInfo` | 相机标定和投影矩阵 / Camera calibration and projection matrix |
| `/oakd/rgb/preview/depth/points` | `sensor_msgs/msg/PointCloud2` | 三维点云 / 3D point cloud |
| `/scan` | `sensor_msgs/msg/LaserScan` | 雷达扫描 / LiDAR scan |
| `/odom` | `nav_msgs/msg/Odometry` | 底盘里程计 / Base odometry |
| `/clock` | `rosgraph_msgs/msg/Clock` | 仿真时间；使用 TF 或传感器时间戳的节点设为 `use_sim_time:=true` / Simulation time; set `use_sim_time:=true` on nodes using TF or sensor timestamps |

[TurtleBot4 Jazzy 传感器桥接 / TurtleBot4 Jazzy sensor bridges](https://github.com/turtlebot/turtlebot4_simulator/blob/jazzy/turtlebot4_gz_bringup/launch/ros_gz_bridge.launch.py) · [Create 3 底盘桥接 / Create 3 base bridges](https://github.com/iRobotEducation/create3_sim/blob/jazzy/irobot_create_gz/irobot_create_gz_bringup/launch/create3_ros_gz_bridge.launch.py)

## 人形资源来源 / Actor credit

`stand.dae` 是 Mingfei 的 `actor_stand` v1 原始网格，采用 CC BY 4.0 许可。场景内的三个实例使用各自的位置和朝向。

`stand.dae` is the unmodified mesh from Mingfei's `actor_stand` v1, licensed under CC BY 4.0. The world places three instances at different positions and orientations.

[Gazebo Fuel 模型 / Gazebo Fuel asset](https://app.gazebosim.org/Mingfei/fuel/models/actor_stand) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
