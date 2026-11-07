# Rescue Car v1 传感器接口与小车使用说明

本说明供 Group 7 合作者审阅，适用于共享的 `rescue_robot` 仿真小车。运行环境为 Ubuntu 24.04、ROS 2 Jazzy 和 Gazebo Harmonic。下表的话题和类型以当前 `config/bridge_rescue.yaml` 为准。启动方式以当前 `launch/rescue_platform.launch.py` 为准。

| 我负责什么 | 先接哪路数据 | 联调时验证什么 |
|---|---|---|
| SLAM 与建图 | `/scan`、`/clock`、`odom → base_link → laser_frame`。自研算法按需订阅 `/odom` 或 `/imu/data` | 扫描点对齐墙面，输出 `/map` 和 `map → odom` |
| RGB 检测 | `/camera/image_raw` 和 `/camera/camera_info` | 能解码左目彩色图像，检测结果带观测时间 |
| 双目测距 | `/stereo/left` 与 `/stereo/right` 下的 `image_raw` 和 `camera_info` | 左右帧按时间配对，已知距离目标的测量误差可记录 |
| 底盘与导航 | 发布 `/cmd_vel`，读取 `/odom` 和 `/scan` | Gazebo 中小车能移动和停车，位姿与 TF 随运动更新 |

### 接口基线

本项目的接口基线以 `rescue_robot` 的 SDF 和 `config/bridge_rescue.yaml` 为准。桥接文件采用 ROS 2 Jazzy 的 `ros_gz_bridge` YAML 格式，逐项指定 **Gazebo 原生话题、ROS 话题、两端消息类型和传输方向**。组内代码使用 ROS 侧接口。`/cmd_vel` 使用 `geometry_msgs/msg/Twist`，双目处理从左右原始图像与标定计算视差，带噪 `/odom` 和 `odom → base_link` 由 `/wheel_noise` 发布。[ros_gz_bridge YAML 配置说明](https://github.com/gazebosim/ros_gz/blob/jazzy/ros_gz_bridge/README.md#example-5-configuring-the-bridge-via-yaml)

组内确认 v1 后，换模型时保持公开的 ROS 话题、类型、单位、时间基准和坐标系语义一致。Gazebo 内部路径可以通过桥接调整。轮距、相机内参、传感器安装位置、帧率、噪声和车身轮廓属于车型参数。改动时同步更新 SDF、标定、TF 和相关配置，订阅程序从消息和 TF 读取实际值。

## 1. 启动平台

在 Ubuntu 中打开 `learning_pkg_python` **包根目录**，也就是能同时看到 `package.xml`、`launch/`、`config/` 和 `models/` 的目录。在终端 A 执行：

```bash
source /opt/ros/jazzy/setup.bash
robot_pkg="$(pwd -P)"
ros2 launch "$robot_pkg/launch/rescue_platform.launch.py"
```

用绝对路径启动源码中的 launch，各组员可以把仓库放在自己的目录。运行环境需安装 Gazebo Harmonic、ROS 2 Jazzy、`ros_gz_bridge`、`rviz2` 和 `tf2_ros`，并能导入 `rclpy`、`geometry_msgs`、`nav_msgs` 和 `sensor_msgs`。若还未配置 ROS 与 Gazebo，参考 [Gazebo Harmonic 安装说明](https://gazebosim.org/docs/harmonic/ros_installation/)。

| 启动内容 | 当前实际读取的文件或输出 |
|---|---|
| Gazebo | `worlds/navigation_test.sdf`，世界名 `car_world`，加载 `models/rescue_robot/car.sdf` |
| Gazebo 到 ROS 桥接 | `config/bridge_rescue.yaml`，节点 `/bridge_rescue` |
| 带噪轮式里程计 | `learning_pkg_python/noisy_odom_node.py`，读取 `config/odom_noise_rescue.yaml`，节点 `/wheel_noise` |
| 静态 TF | launch 发布雷达、IMU 和左右相机安装变换 |
| RViz | `config/robot_view.rviz`，使用仿真时间，默认固定坐标系为 `odom`，已配置 `/scan` |

保持终端 A 运行。各组在另一个终端加载 ROS 环境，再启动订阅程序、SLAM 或双目处理。平台启动后提供传感器和里程计，地图和目标检测结果由相应小组的节点发布。

在终端 B 逐条验证，命令收到一条实际消息后会退出。若其中一条持续等待，按 `Ctrl+C` 返回并检查第 8 节。

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic echo /clock --once
ros2 topic echo /scan --field header --once --qos-reliability best_effort
ros2 topic echo /odom --field child_frame_id --once
ros2 topic echo /camera/image_raw --field header --once --qos-reliability best_effort
```

预期 `/scan` 的 `frame_id` 为 `laser_frame`，`/odom` 的 `child_frame_id` 为 `base_link`，RGB 图像的 `frame_id` 为 `left_camera_optical_frame`。在 RViz 中，雷达点应落在场景墙面和障碍物上。

## 2. 话题与消息类型

**编写 ROS 节点时使用表中的 ROS 话题。** `GZ` 指 Gazebo Transport，`<车>` 代表 `/model/rescue_robot`。下表完整列出 12 条桥接映射。传感器的标称频率和数据字段见第 3、4 节。[ROS–Gazebo 桥接配置说明](https://github.com/gazebosim/ros_gz/tree/jazzy/ros_gz_bridge)

| ROS 话题 | ROS 消息类型 | 方向 | Gazebo 话题 | Gazebo 消息类型 |
|---|---|---|---|---|
| `/cmd_vel` | `geometry_msgs/msg/Twist` | ROS → GZ | `<车>/cmd_vel` | `gz.msgs.Twist` |
| `/clock` | `rosgraph_msgs/msg/Clock` | GZ → ROS | `/world/car_world/clock` | `gz.msgs.Clock` |
| `/scan` | `sensor_msgs/msg/LaserScan` | GZ → ROS | `<车>/scan` | `gz.msgs.LaserScan` |
| `/imu/data` | `sensor_msgs/msg/Imu` | GZ → ROS | `<车>/imu` | `gz.msgs.IMU` |
| `/wheel/odometry_raw` | `nav_msgs/msg/Odometry` | GZ → ROS | `<车>/odometry` | `gz.msgs.Odometry` |
| `/ground_truth/odom` | `nav_msgs/msg/Odometry` | GZ → ROS | `<车>/ground_truth/odometry` | `gz.msgs.Odometry` |
| `/stereo/left/image_raw` | `sensor_msgs/msg/Image` | GZ → ROS | `<车>/stereo/left/image` | `gz.msgs.Image` |
| `/stereo/left/camera_info` | `sensor_msgs/msg/CameraInfo` | GZ → ROS | `<车>/stereo/left/camera_info` | `gz.msgs.CameraInfo` |
| `/stereo/right/image_raw` | `sensor_msgs/msg/Image` | GZ → ROS | `<车>/stereo/right/image` | `gz.msgs.Image` |
| `/stereo/right/camera_info` | `sensor_msgs/msg/CameraInfo` | GZ → ROS | `<车>/stereo/right/camera_info` | `gz.msgs.CameraInfo` |
| `/camera/image_raw` | `sensor_msgs/msg/Image` | GZ → ROS | `<车>/stereo/left/image` | `gz.msgs.Image` |
| `/camera/camera_info` | `sensor_msgs/msg/CameraInfo` | GZ → ROS | `<车>/stereo/left/camera_info` | `gz.msgs.CameraInfo` |

ROS 节点还会生成以下接口。SLAM、双目处理和目标检测需要各组按任务单独启动。

| ROS 话题 | 类型 | 发布者和使用方式 |
|---|---|---|
| `/odom`、`/wheel/odometry` | `nav_msgs/msg/Odometry` | `/wheel_noise`。两者是同一份带噪积分结果，导航和建图按约定使用 `/odom` 与对应 TF |
| `/tf`、`/tf_static` | `tf2_msgs/msg/TFMessage` | `/wheel_noise` 发布 `odom → base_link`，launch 发布传感器固定 TF。运行 SLAM 或定位后，由当前定位节点提供 `map → odom` |
| `/map` | `nav_msgs/msg/OccupancyGrid` | 由 SLAM 或固定地图服务器提供 |
| `/stereo/disparity` | `stereo_msgs/msg/DisparityImage` | 启动第 4 节的双目处理示例后检查此输出 |
| 建议 `/rescue_target` | `geometry_msgs/msg/PointStamped` | 待组内确认。由视觉节点交接有效目标点，消息包含观测时间和坐标系 |

### 三个通用规则

1. **时间。** 传感器的采样时间在 `header.stamp.sec` 和 `header.stamp.nanosec`。对齐数据时用采样时间，计算时用 `sec + nanosec × 10⁻⁹`。SLAM、RViz 和需要查 TF 的自定义节点设置 `use_sim_time:=true`，与 Gazebo `/clock` 使用同一时间基准。
2. **坐标系。** 用 `header.frame_id` 确定数据在哪个坐标系。`base_link` 的 x 向前、y 向左、z 向上。相机光学坐标的 x 向右、y 向下、z 向前。安装偏移通过 TF 处理，查询时传入消息的采样时间。
3. **QoS。** 传感器订阅可从 `qos_profile_sensor_data` 开始。若话题存在却收不到，使用 `ros2 topic info /话题名 -v` 检查实际发布者和 QoS。相机消息体较大，单条消息头能证明收到一帧，连续接收和双目配对仍需测量。 [ROS 2 QoS 兼容规则](https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html)

## 3. SLAM 与建图组

### 3.1 二维雷达 `/scan`

配置为水平 360°、360 个采样点、10 Hz、量程 `0.08–12.0 m`、距离分辨率 `0.01 m`，距离噪声标准差 `0.01 m`。雷达相对 `base_link` 的位置是 `(0.03, 0, 0.48) m`。障碍物需要与约 `0.48 m` 高的扫描平面相交，才能被这路水平雷达测到。

| `LaserScan` 字段 | 如何读取和使用 |
|---|---|
| `header.stamp`、`header.frame_id` | 一帧扫描的参考时间和 `laser_frame`。消息规范规定时间戳对应首条射线 |
| `ranges[i]` | 第 `i` 条射线的距离，单位 m。转点时筛掉非有限值及超出 `range_min`、`range_max` 的数据。做清空射线时，按建图算法的无回波规则处理 |
| `angle_min`、`angle_max`、`angle_increment` | 起始角、结束角、角增量，单位 rad。用消息实际值计算，零角朝雷达正 x，正角绕正 z 逆时针 |
| `scan_time`、`time_increment` | 两帧间隔和帧内射线间隔，单位 s。做运动补偿前读取实际值 |
| `intensities` | 回波强度，取决于传感器实现，可能为空 |

二维点的计算是 `θ = angle_min + i × angle_increment`，随后 `x = ranges[i] × cos(θ)`、`y = ranges[i] × sin(θ)`。得到的点还在 `laser_frame` 中。用扫描时刻的 `odom ← laser_frame` 或 `map ← laser_frame` 变换后才能和对应坐标系的地图叠加。[LaserScan 消息定义](https://github.com/ros2/common_interfaces/blob/jazzy/sensor_msgs/msg/LaserScan.msg)

```bash
ros2 topic echo /scan --once --qos-reliability best_effort
ros2 run tf2_ros tf2_echo odom laser_frame --ros-args -p use_sim_time:=true
```

### 3.2 里程计和 IMU

**带噪轮式里程计。** `/wheel_noise` 使用原始轮速和原始消息时间戳积分平面位姿，输出 `/odom` 并发布 `odom → base_link`。配置中的线速度噪声标准差为 `0.01 m/s`，偏航角速度噪声标准差为 `0.02 rad/s`，偏置为零，随机种子为 `42`。

| `Odometry` 字段 | 含义 |
|---|---|
| `header.frame_id`、`child_frame_id` | `/odom` 中分别为 `odom`、`base_link` |
| `pose.pose.position`、`pose.pose.orientation` | 位置（m）和四元数，表达在 `header.frame_id` 中 |
| `twist.twist.linear`、`twist.twist.angular` | 线速度（m/s）和角速度（rad/s），表达在 `child_frame_id` 中。差速底盘主要关注 `linear.x`、`angular.z` |
| `pose.covariance`、`twist.covariance` | 6×6 协方差，按行展开。坐标顺序为 `x, y, z, roll, pitch, yaw`，对角项索引为 `0, 7, 14, 21, 28, 35` |

做离线误差评估可订阅 `/ground_truth/odom`。比较真值和估计时，先对齐时间和坐标原点。建图或定位的在线轮式输入使用 `/odom` 或算法约定的轮速来源。[Odometry 消息定义](https://github.com/ros2/common_interfaces/blob/jazzy/nav_msgs/msg/Odometry.msg)

**IMU。** `/imu/data` 的标称频率为 `50 Hz`，安装位置是 `(0, 0, 0.10) m`。配置在 z 轴角速度上加入标准差 `0.01 rad/s` 的高斯噪声。`orientation` 是四元数，`angular_velocity.{x,y,z}` 单位是 rad/s，`linear_acceleration.{x,y,z}` 单位是 m/s²。三组 `*_covariance` 各是 3×3 矩阵。全零表示协方差未知，首项为 `-1` 表示对应测量缺失。融合前在静止状态检查实际加速度方向、重力和协方差。当前带噪轮式里程计独立使用轮速，IMU 可由组员按需接入估计器。[Imu 消息定义](https://github.com/ros2/common_interfaces/blob/jazzy/sensor_msgs/msg/Imu.msg)

```bash
ros2 topic echo /odom --once
ros2 topic echo /imu/data --once --qos-reliability best_effort
```

### 3.3 接入 SLAM 的约定

如果使用 SLAM Toolbox，在组内参数文件现有的 `slam_toolbox.ros__parameters` 里核对下列项，尤其是 `base_frame: base_link`。其余求解器参数可保留所用模板。SLAM Toolbox 通过 TF 获取每帧扫描对应的里程计位姿，自研算法也可以直接订阅 `/odom` 读取其消息字段。[SLAM Toolbox Jazzy 参数模板](https://github.com/SteveMacenski/slam_toolbox/blob/jazzy/config/mapper_params_online_async.yaml)

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

建图时由 SLAM 发布 `/map`（`nav_msgs/msg/OccupancyGrid`）和 `map → odom`。同一运行模式下只安排一个 `map → odom` 发布者。将 RViz 的 Fixed Frame 改为 `map`，添加 `/map` 显示并保留 `/scan`，检查扫描点能否与地图墙面重合。交给导航组时，提供对应场景名、地图 YAML 与图片，以及地图坐标系和初始位姿约定。

使用 SLAM Toolbox 时，在包根目录另开终端。如果组里还没有配置，可先从已安装的 `slam_toolbox` 包复制默认参数，再修改上面列出的字段。命令中的 `slam_rescue.yaml` 是供组员创建的文件名。

```bash
source /opt/ros/jazzy/setup.bash
robot_pkg="$(pwd -P)"
slam_share="$(ros2 pkg prefix --share slam_toolbox)"
slam_config="$robot_pkg/config/slam_rescue.yaml"
if [ ! -e "$slam_config" ]; then
  cp "$slam_share/config/mapper_params_online_async.yaml" "$slam_config"
fi
```

保存修改后，从同一个终端启动建图。等收到地图后再缓慢驾驶小车，观察地图是否扩展。[SLAM Toolbox Jazzy 启动文件](https://github.com/SteveMacenski/slam_toolbox/blob/jazzy/launch/online_async_launch.py)

```bash
ros2 launch slam_toolbox online_async_launch.py \
  slam_params_file:="$slam_config" use_sim_time:=true
```

## 4. RGB 检测与双目测距组

### 4.1 选择图像和标定话题

- **只做 RGB 检测**，订阅 `/camera/image_raw` 和 `/camera/camera_info`。它们与双目左路来自同一相机。项目处理时可以选一套左目接口，减少重复订阅。
- **做双目测距**，订阅左右两路 `/stereo/.../image_raw` 和各自的 `camera_info`。按采样时间配对左右图与标定，使用已校正的图像计算视差。
- **查看图像**，运行 `ros2 run rqt_image_view rqt_image_view`（需安装该工具），在下拉框选择左右话题。查看字段时可以只打印 `encoding` 或 `header`，避免在终端打印整张图片字节。

```bash
ros2 topic echo /camera/image_raw --field encoding --once --qos-reliability best_effort
ros2 topic echo /stereo/left/camera_info --once --qos-reliability best_effort
ros2 topic echo /stereo/right/camera_info --once --qos-reliability best_effort
```

### 4.2 读懂 `Image` 和 `CameraInfo`

| 消息 | 字段 | 含义 |
|---|---|---|
| `Image` | `width`、`height` | 宽、高，单位 px。当前配置为 `640 × 480` |
| `Image` | `encoding`、`step`、`is_bigendian`、`data` | 像素编码、每行字节数、字节序和图像数据。SDF 配置为 `R8G8B8`，以 ROS 消息的实际编码为准 |
| `Image` / `CameraInfo` | `header` | 采样时间和相机光学坐标系。用同一路的图像和标定配对 |
| `CameraInfo` | `distortion_model`、`d` | 畸变模型和对应系数 |
| `CameraInfo` | `k` | 原图的 3×3 内参，按行展开。`k[0] = fx`、`k[4] = fy`、`k[2] = cx`、`k[5] = cy` |
| `CameraInfo` | `r`、`p` | 3×3 校正旋转和 3×4 校正图投影矩阵，均按行展开。反投影校正图时用 `p[0]`、`p[5]`、`p[2]`、`p[6]` 读焦距和主点 |

以上数组在 Python 中使用小写字段名，如 `msg.k`、`msg.p`。图像转 OpenCV 可以使用 `CvBridge().imgmsg_to_cv2(msg, desired_encoding="bgr8")`，需要安装 `cv_bridge`。这个转换按实际消息编码处理通道和步长。[Image 消息定义](https://github.com/ros2/common_interfaces/blob/jazzy/sensor_msgs/msg/Image.msg) · [CameraInfo 消息定义](https://github.com/ros2/common_interfaces/blob/jazzy/sensor_msgs/msg/CameraInfo.msg)

两目各 `10 Hz`、水平视场 `90°`，近远裁剪距离 `0.05–15.0 m`。左、右光心相对 `base_link` 分别是 `(0.421, +0.06, 0.32)` 和 `(0.421, −0.06, 0.32)` m。基线 `B = 0.12 m`。SDF 配置 `fx = fy = 320 px`、`cx = 320 px`、`cy = 240 px`，左 `p[3] = 0`，右 `p[3] = −38.4`。程序用实际收到的 `CameraInfo`，核对右目基线 `B = −p[3] / p[0]`，裁剪距离与视差算法的有效测距范围分别验证。

### 4.3 从目标检测得到距离

1. **先配对。** 录制或订阅左右图和各自标定，按 `header.stamp` 检查配对。左右依次执行两次 `echo --once` 只能检查接口有数据。安装 `stereo_image_proc` 和 `image_proc` 后，可用下方命令启动图像校正与视差处理，先用严格同步模式。 [Jazzy 双目处理启动文件](https://github.com/ros-perception/image_pipeline/blob/jazzy/stereo_image_proc/launch/stereo_image_proc.launch.py)
2. **在同一像素网格检测和测距。** 可在 `/stereo/left/image_rect_color` 上检测，再用 `/stereo/disparity` 取对应像素。如果检测模型使用缩放图或原图，先把检测框变换到校正左图坐标。
3. **从有效视差计算深度。** 在检测区域与 `valid_window` 的交集中取有限、为正且在搜索范围内的视差 `d`。用 `Z = f × T / d` 逐点算深度，其中 `f`、`T` 从 `stereo_msgs/msg/DisparityImage` 读取。可用有效深度的中位数抑制背景和离群点。有效样本不足时标记测距无效。[DisparityImage 消息定义](https://github.com/ros2/common_interfaces/blob/jazzy/stereo_msgs/msg/DisparityImage.msg)
4. **输出坐标和测距定义。** `Z` 是沿光轴的前向深度。对有效像素 `(u,v)`，用左目校正投影参数计算 `X=(u−cx)Z/fx`、`Y=(v−cy)Z/fy`。如果需要到光心的直线距离，计算 `sqrt(X²+Y²+Z²)`。三维点先标在 `left_camera_optical_frame`，用观测时刻 TF 转到 `base_link` 或已定位的 `map`。交接给任务节点时，可以约定使用带时间戳的 `geometry_msgs/msg/PointStamped`。

```bash
ros2 launch stereo_image_proc stereo_image_proc.launch.py \
  namespace:=stereo left_namespace:=left right_namespace:=right \
  launch_image_proc:=True approximate_sync:=False
```

在另一终端执行 `ros2 topic echo /stereo/disparity --field header --once --qos-reliability best_effort`。首先让车静止，在左光心正前方放一个有纹理的目标。按配置，光轴深度为 **2.0 m** 时应得到约 **19.2 px** 的视差。用实际 `CameraInfo` 和多帧结果验证，再测试移动时的配对。图像、标定由平台提供，视差由上面的处理节点或组内算法发布。

## 5. 用 Python 读取实际数据

下面是一份可单独运行的订阅探针。把代码保存为自己的 `sensor_probe.py`。它对每个话题只打印第一条收到的消息摘要，组员可把 `show` 中的数据读取移到自己的回调函数。传感器用 `qos_profile_sensor_data`，`/odom` 和真值用普通订阅队列。

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
            nearest = f"{min(valid):.3f} m" if valid else "无有效回波"
            detail = f"采样数={len(msg.ranges)}, 最近点={nearest}"
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

在 `sensor_probe.py` 所在目录运行，看到各话题摘要后按 `Ctrl+C`：

```bash
source /opt/ros/jazzy/setup.bash
python3 sensor_probe.py --ros-args -p use_sim_time:=true
```

`ros2 interface show sensor_msgs/msg/LaserScan` 可以列出原始消息定义。把类型替换为 `sensor_msgs/msg/Imu`、`sensor_msgs/msg/Image`、`sensor_msgs/msg/CameraInfo` 或 `nav_msgs/msg/Odometry` 即可查看其他接口。

## 6. TF 结构与小车控制

```text
map                              由当前 SLAM 或定位节点提供
└─ odom                          map → odom 由定位侧发布
   └─ base_link                  odom → base_link 由 /wheel_noise 发布
      ├─ laser_frame             (0.03, 0, 0.48) m
      ├─ imu_link                (0, 0, 0.10) m
      └─ stereo_camera_link      (0.421, 0, 0.32) m
         ├─ left_camera_link     相对相机架 (0, +0.06, 0) m
         │  └─ left_camera_optical_frame
         └─ right_camera_link    相对相机架 (0, −0.06, 0) m
            └─ right_camera_optical_frame
```

相机光学 TF 在 launch 里以滚转 `−π/2`、俯仰 `0`、偏航 `−π/2` 配置。单独启动平台时，使用 `odom` 作为 RViz 固定坐标系。检查雷达安装偏移时，查询 `base_link → laser_frame`，正常应为 `[0.030, 0.000, 0.480]` 和零旋转。静态 TF 在 `tf2_echo` 中显示 `At time 0.0` 是正常的。

在空地上进行短距离测试时，确保 `/cmd_vel` 只有这次测试作为控制来源。先发送 20 条 `0.15 m/s` 的前进指令，再发送零速度。若中途用 `Ctrl+C` 打断，运行停车命令。

```bash
ros2 topic pub --rate 10 --times 20 /cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.15}, angular: {z: 0.0}}'
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.0}, angular: {z: 0.0}}'
```

`linear.x > 0` 表示前进，`angular.z > 0` 表示向左转。实际使用中，遥控、测试命令和 Nav2 共用速度入口。切换任务时先停止前一控制来源，再启用下一控制来源。

### 固定地图导航联调

平台运行正常后，可以用当前 `navigation_test.sdf` 与 `rescue_navigation_test.yaml` 做一次固定地图测试。结束正在运行的 SLAM，由 AMCL 接管 `map → odom`。当前 `nav2_test.yaml` 已启用 NavFn 的 `use_astar: true`，但全局代价地图的 `robot_radius` 仍为 `1.75 m`。如果全局规划在窄处过于保守，按新车尺寸复核该值与 RViz 中的全局代价地图。Nav2 最终输出到 `/cmd_vel` 的类型应与本车桥接的 `geometry_msgs/msg/Twist` 一致。[NavFn 配置](https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/planners_plugins/configuring_navfn/) · [Nav2 Jazzy 启动文件](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_bringup/launch/bringup_launch.py)

在包根目录另开终端，启动地图服务器、AMCL 和 Nav2：

```bash
source /opt/ros/jazzy/setup.bash
robot_pkg="$(pwd -P)"
ros2 launch nav2_bringup bringup_launch.py \
  map:="$robot_pkg/maps/rescue_navigation_test.yaml" \
  params_file:="$robot_pkg/config/nav2_test.yaml" \
  slam:=False use_composition:=False use_sim_time:=true autostart:=true
```

如果需要在 RViz 点选导航目标，可在另一个终端运行 `ros2 launch nav2_bringup rviz_launch.py use_sim_time:=true`，使用带 Nav2 工具的 RViz 配置。将 Fixed Frame 设为 `map`。若定位需要初始位姿，用 **2D Pose Estimate** 指定小车实际位置与朝向。等导航节点激活后，在前方空地用 **Nav2 Goal** 发一个约 1 m 的目标。检查 RViz 有路径、Gazebo 小车移动，并且目标成功完成。

## 7. 联调时录什么

建图组记录扫描、里程计、坐标变换和时钟。开始建图后可加录 `/map`，评估误差时可加录真值：

```bash
ros2 bag record -o rescue_mapping_run /clock /tf /tf_static /scan /odom
```

视觉组同时录左右图与标定。同步或测距故障时，核对配对消息的 `header.stamp`，并记录无效视差占比：

```bash
ros2 bag record -o rescue_stereo_run /clock /tf /tf_static \
  /stereo/left/image_raw /stereo/left/camera_info \
  /stereo/right/image_raw /stereo/right/camera_info
```

交接时附上使用的场景文件、起始位姿和启动命令。视觉测距结果还应标明采用的是光轴深度还是直线距离，以及目标点的坐标系。

## 8. 常见问题

| 现象 | 从哪里检查 |
|---|---|
| Gazebo 找不到 `model://rescue_robot` | 确认 `model.config` 指向 `car.sdf`，并用本包 launch 启动。手动运行 Gazebo 时，把模型的上级 `models` 目录加入 `GZ_SIM_RESOURCE_PATH` |
| 有 Gazebo 模型，ROS 话题一直等待 | 检查仿真是否播放。用 `gz topic -l` 查看 Gazebo 原生话题，再核对 `bridge_rescue.yaml` 和 ROS 域。世界名应与时钟桥接的 `car_world` 匹配 |
| `/odom` 无数据 | 用 `ros2 node info /wheel_noise` 检查节点，再用 `ros2 topic echo /wheel/odometry_raw --field header --once` 确认原始里程计进入 ROS |
| RViz 有雷达数据但 TF 报错 | 平台测试使用 `odom`。检查 `base_link → laser_frame` 和 `odom → base_link`，以及相关节点的 `use_sim_time` |
| 图像有数据但提示消息丢失 | 用图像查看器或同步录包检查连续帧和左右时间配对，再定位传输、QoS 或仿真负载 |
| 有左右图像但没有目标深度 | 检查校正图、两路标定、视差输出、时间同步和有效视差范围 |

此前的接口联调日志已读到 `/clock`、`/wheel/odometry_raw`、`/odom`、`/scan`、IMU、左右图像、左右 `CameraInfo` 及 RGB 别名，且 `base_link → laser_frame` 实测为 `[0.030, 0.000, 0.480]` m、零旋转。换模型或修改传感器后，重复第 1 节的消息检查，再按各组章节验证扫描对齐、图像连续性、视差精度和运动控制。
