# 技术比较与第一阶段选型

日期：2026-11-10。本文记录技术选型依据；第二阶段已补充CPU二维检测实测，见[检测报告](phase2_detection.md)。实体硬件性能、全链路采集延迟与跟随效果仍为 **NOT VERIFIED**。

## 基础环境选择

选择 **Ubuntu 24.04 容器 + ROS 2 Jazzy + Gazebo Harmonic**。这是 [TurtleBot 4 官方支持组合](https://turtlebot.github.io/turtlebot4-user-manual/software/turtlebot4_simulator.html)。当前宿主是 Ubuntu 26.04，因此 ROS/Gazebo 安装在容器内部。Jazzy 的目标系统和支持周期见 [REP-2000](https://www.ros.org/reps/rep-2000.html#jazzy-jalisco-may-2024-may-2029)。

Humble/Ubuntu 22.04/Fortress 是仍值得保留的另一条官方组合；当前没有实体 Humble 机器人需要匹配，因此不同时安装两套环境。未来接实物先核实机器人镜像、底盘和驱动版本，再决定是否换为 Humble，不能依赖跨发行版 DDS 兼容的假设。

## ROS 2 核心职责

| 组件 | 职责 | 本项目使用阶段 |
|---|---|---|
| ROS 2 Jazzy | 节点、接口、工具和发行版依赖 | 必须，当前基础 |
| TF2 | 按观测时间把相机坐标转到 base/odom/map | 必须，先验证再做 3D 融合 |
| DDS/RMW | 传输与发现、QoS，不能代替同步/安全协议 | 使用发行版默认，记录实际实现；容器运行时无外部网络 |
| Topics | 高频图像、深度、扫描、检测和状态 | 必须；图像 SensorDataQoS，记录可靠性兼容情况 |
| Services | 设置/清除目标、查询状态等短操作 | 设计保留；不用于长时间导航 |
| Actions | 可取消、反馈进度的导航/跟随任务 | 后续先连接 Mock server |
| Lifecycle Nodes | 配置、激活、停用和异常恢复 | 感知/跟随协调节点采用；默认 inactive |
| Nav2 + Costmap 2D | 全局路径、局部轨迹、障碍物代价 | 依赖安装；当前不启动导航 |
| SLAM Toolbox | 构图并提供 map→odom | 后续建图时使用 |
| AMCL | 在已知地图上定位 | 后续与 SLAM 二选一作为 map→odom 权威 |

## 检测与深度路线

准确率取决于模型、输入尺寸、场景/域差异与阈值；速度取决于算力、前后处理和传输。以下为工程特征比较，不是实测排名。

| 方法 | 检测、深度方式 | 资源与集成 | OAK/当前仿真适配 | 决策 |
|---|---|---|---|---|
| OpenCV DNN + MobileNet/其他检测器 | 主机检测；通过对齐深度 ROI 取稳健测量 | 可用 CPU；要自行处理模型和消息适配；性能 NOT VERIFIED | 能消费模拟 RGBD，不能模拟设备端速度 | 可作较小模型对照基线 |
| Ultralytics YOLO | 模型系列丰富；框/掩码配合 RGBD 提升 | Python/PyTorch 或导出 ONNX；CPU/GPU可选；权重和代码条款单独核查 | 不依赖 OAK；CPU 可用于当前 VM | 不默认最优；后续同一 rosbag 实测 |
| 当前 yolo_ros + ONNX Runtime | C++ 插件式检测/追踪/3D 提升 | 社区 ROS 2 集成现成；当前源码与旧教程差异大，需固定提交 | 可直接消费虚拟 RGB/深度/CameraInfo | 已编译5.0.0并验证CPU二维检测；跟踪/3D插件未启用 |
| DepthAI SpatialDetectionNetwork | 设备端检测结合双目深度，发布空间测量 | 主机压力可降低，受设备支持网络/编译格式约束 | 实体 OAK 路线强；当前没有设备/VPU | 纯仿真阶段不安装；不假报 VPU FPS |
| MediaPipe Pose | 人体关键点，可用于动作/姿态 | 可用 CPU/部分硬件后端；需额外 ROS 适配 | 可处理虚拟 RGB；身体坐标不等于相机中的绝对距离 | 非第一阶段必需 |
| NVIDIA Isaac ROS | TensorRT/Triton 和加速图像管线 | 依赖匹配版本的 NVIDIA 平台/驱动/存储 | 本 VM 没有可见 CUDA，不匹配当前资源 | 当前不安装 |

MediaPipe world landmarks 的原点在髋部，不能直接拿来当机器人到人的测距。[官方源码文档](https://github.com/google-ai-edge/mediapipe/blob/master/docs/solutions/pose.md)。Isaac ROS 4.0 的支持平台需按[对应版本文档](https://nvidia-isaac-ros.github.io/v/release-4.0/repositories_and_packages/isaac_ros_dnn_inference/index.html)选择，不能认为任意 Jetson 都兼容任意最新版。

### DepthAI 版本门槛

Humble/Jazzy 的 v3 驱动包带 `_v3` 后缀；无后缀旧驱动与 v3 文档不能互换。[官方说明](https://docs.luxonis.com/software-v3/depthai/ros/driver)。未来实体实验记录：相机型号/MXID、RVC代际、USB链路、ROS包版本、DepthAI库版本、模型格式与编译工具、固件信息、标定、同步与对齐参数。本阶段没有这些真实观测。

虚拟 RGB-D 相机可以测试 ROS 接口，但没有证据支持它仿真 Myriad X 推理器；DepthAI 路线A与主机路线B的公平实体性能对比目前 **NOT VERIFIED**。

## 跟踪与目标身份

| 方法 | ID维持方式 | 遮挡/交叉局限 | 当前建议 |
|---|---|---|---|
| Kalman Filter | 预测状态及协方差；本身没有数据关联 | 不会辨认人物身份，长期预测会漂移 | 作为运动模型，不独立宣称完成跟踪 |
| ByteTrack | 按置信度分阶段做运动/框关联 | 长遮挡、相似轨迹交叉仍会换 ID | 优先轻量基线 |
| DeepSORT | 运动门控与外观距离、匹配级联 | 相似衣着/背面、旧模型域差异 | 参考设计，不引入旧 TensorFlow整栈 |
| BoT-SORT | 运动与可选外观、全局相机运动补偿 | ReID额外计算，不能保证身份 | 交叉/移动相机测试中的对照 |
| DepthAI ObjectTracker | 设备/主机 tracklet，部分版本可用空间关联 | 是否使用空间信息由配置决定，身份保证有限 | 仅实体路线评估 |
| 3D数据关联 | 同一 odom 坐标下位置/协方差门控，融合外观与2D | 深度失效、TF延迟、拥挤时仍会误配 | 在2D基线上逐步增加 |

目标选择独立于 tracker：使用 `{session_id, track_id}` 锁定目标；相机/跟踪器重启后旧 ID 不自动继承。短遮挡可保留候选轨迹，观测超时后停止目标驱动；重现后需时空/外观/置信度一致，存在歧义则要求显式重新选择。不能通过“换成最近的人”掩盖目标丢失。

论文及原始实现见 `industry_research.md`。本项目尚无 IDF1、HOTA、错误切换率的实测结果。

## 导航方案A与B

| 比较项 | A：Nav2 动态目标/路径更新 | B：独立闭环跟随控制器 |
|---|---|---|
| 优点 | 可复用地图、规划器、costmap、行为树及任务取消 | 延迟链路较短，开阔区域容易表达距离/方位误差控制 |
| 局限 | 目标频繁变化会导致重规划抖动；需处理人体附近不可通行代价 | 需要补足避障、可达性、停机、仲裁及恢复；只靠视觉左右误差不能绕障 |
| 遮挡/拐弯 | 可利用已知自由空间与最近有效位置；仍需限制预测寿命 | 目标离开视野后控制依据迅速失效 |
| 安全接口 | 输出必须通过独立限速/Collision Monitor/最终使能 | 同样必须经过独立保护链，不直连底盘 |
| 本项目选择 | 后续复杂场景主线，先通过 Mock action验证更新/取消 | 作为开阔场景对照，暂不实现输出运动 |

Nav2 Jazzy 已有动态目标行为树教程；源码中存在专用 Following Server，必须区分源码中存在与当前镜像已安装。[官方教程](https://docs.nav2.org/jazzy/tutorials/general_tutorials/navigation2_dynamic_point_following/navigation2_dynamic_point_following/)。不能把“不断发送 NavigateToPose”作为唯一成熟方法，也不能把 Following Server 默认寻找目标旋转当作本项目默认行为。

本机补充核验：已安装Nav2 1.3.13，`FollowObject` action定义可查询，但当前镜像没有安装`opennav_following`包。因此目前不能把专用Following Server记为可运行能力；下一阶段先用Mock与动态目标行为树，另行核实该可选包。

### 控制器与动态障碍

- Regulated Pure Pursuit：路径跟踪、曲率/障碍距离调速和前向碰撞检查，适合计算预算有限的路径跟随；不能替代全局规划和完整动态人群预测。[Jazzy源码说明](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_regulated_pure_pursuit_controller/README.md)。
- MPPI：采样预测控制并用代价评价轨迹，具有更多调参和计算成本；当前软件渲染 VM 先测预算，再与 RPP 比较。[Jazzy源码说明](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_mppi_controller/README.md)。
- Costmap 2D：静态/障碍/膨胀层分别处理地图与传感器障碍；有障碍层不意味着具有行人长期行为预测。
- 社会化导航：把个人空间、群体关系和不横穿群体作为额外策略，SPENCER 提供研究经验；标准 Nav2 不自动保证社会规范。
- Collision Monitor：对传感器超时和区域触发进行速度限制/停止；必须接在最终速度链上并测试故障注入。[Jazzy参数](https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/collision_monitor/configuring_collision_monitor_node/)。

## 轻量工具链

| 等级 | 工具 | 用途/当前动作 |
|---|---|---|
| 必须 | Ubuntu24容器、ROS2、Git、CMake/colcon、Python/C++ | 安装可复现仿真基础；保留源码和依赖锁 |
| 必须 | Gazebo Harmonic、TurtleBot4 Simulator、ros_gz | 虚拟硬件与消息桥接 |
| 必须 | OpenCV/cv_bridge、rosbag2 | 读写图像、采集可复现实验数据 |
| 必须（分阶段） | pytest / launch_testing | 离线数值与集成/失联测试；不编写只重复实现的空测试 |
| 推荐 | RViz2 | 图像、TF、点云、轨迹可视化；官方仿真依赖可能已带入，当前不启动GUI |
| 推荐 | Docker | 隔离宿主26.04与Jazzy依赖；运行时 network none |
| 推荐 | VS Code/Codex、Dev Container配置 | 编辑、远程开发；不在服务器再装一套桌面IDE |
| 可选 | Foxglove、PlotJuggler | 大规模日志/曲线分析，第一步不加装 |
| 当前不需要 | PyTorch训练、CUDA、TensorRT、Isaac Sim、MediaPipe全套 | 当前无训练任务或匹配GPU，不预装 |

锁定基础镜像 digest、源码 SHA 和安装包清单。Dockerfile 使用固定基础镜像但 apt 仓库会演进；只有保留本次构建镜像/镜像ID与 packages.lock 才能复用这一运行环境，不能承诺未来任意日期重建得到逐字节相同镜像。
