# TurtleBot 4 人体感知与跟随：成熟技术调研

研究日期：2026-11-10（Europe/London）。阶段：第一步，技术调研及仿真开发环境。

## 结论与证据边界

用户已明确全部为虚拟硬件。本项目当前采用 Ubuntu 24.04 容器、ROS 2 Jazzy、Gazebo Harmonic，先建立静止 RGB-D、雷达与 TF 数据链路，再比较检测和跟踪方法。当前主线是主机 CPU 推理；没有可访问的 OAK-D/VPU，也没有证据表明 VMware 向来宾提供 NVIDIA CUDA。

专业系统应把检测、距离测量、目标身份、运动规划、执行保护分开设计。能画框不等于能够稳定跟随；有 Track ID 也不等于能够跨越任意遮挡识别同一人。第一阶段只完成调研与基础环境；第二阶段的二维检测实现和测量见[检测报告](phase2_detection.md)，目标跟踪和自主跟随尚未实现。

事实分级：**官方支持**指维护者文档/源码明确声明；**社区实现**指第三方项目；**设计建议**是本项目尚待验证的选择；**NOT VERIFIED**表示未在当前环境验证。公开项目无法证明所有商用机器人的内部技术栈。

## 核验方式

通过 GitHub API 获取默认分支、默认分支最后提交、归档状态、许可证元数据，并保存提交固定的 README/许可证。完整记录见 `../evidence/repository_inventory.json`。维护判断依据提交活动，不能把 GitHub `updated_at`（可能只是收藏活动）当成维护日期。

以下短 SHA 均对应该记录中的完整 SHA。源代码下载与校验记录另见 `../evidence/source_downloads.lock.json`；Nav2 实际下载 Jazzy 分支，而不是默认 main。

## 1. TurtleBot 4 Simulator：官方仿真底座

- 项目：[turtlebot/turtlebot4_simulator](https://github.com/turtlebot/turtlebot4_simulator)，Apache-2.0。
- 核验版本：Jazzy 分支 `b7d0f3b97325`，默认分支最后提交 2024-10-30，未归档；包源码版本 2.0.2。分支较旧不等于没有发行维护，apt 二进制版本另行记录。
- 架构：Gazebo 物理/渲染传感器，`ros_gz_bridge` 转为 ROS 消息，Create 3 模拟节点和 TurtleBot 节点提供机器人接口；可选启动导航/定位。
- 硬件：虚拟 Create 3、OAK RGB-D 和雷达模型；实际运行在主机 CPU/GPU，不执行原装 OAK-D 的 Myriad/VPU 固件。
- ROS：官方手册列出 Jazzy/Ubuntu 24.04/Harmonic，以及 Humble/22.04/Fortress。Galactic 已停止支持。
- 复用：是，本项目首选官方仿真底座。需要检查每个相机 topic、光学 frame、时钟和桥接方向。
- 借鉴：优先保留官方描述、标准消息和模拟接口，在项目自己的 launch/world 中做配置；不要把 Gazebo 深度直接当成真实双目误差模型。

来源：[安装与启动](https://turtlebot.github.io/turtlebot4-user-manual/software/turtlebot4_simulator.html)、[相机桥接源码](https://github.com/turtlebot/turtlebot4_simulator/blob/jazzy/turtlebot4_gz_bringup/launch/ros_gz_bridge.launch.py)。

## 2. TurtleBot 4 Examples：早期原装相机跟随参考

- 项目：[turtlebot/turtlebot4_examples](https://github.com/turtlebot/turtlebot4_examples)，Apache-2.0。
- 版本/维护：默认 Galactic，`82c8bdfedf71`，最后提交 2022-05-25；未归档，不能作为现代 Jazzy 开箱可用的证据。
- 架构：Mobilenet Spatial Publisher 使用检测和双目深度发布空间检测；FollowBot 消费人物检测进行跟随。
- 硬件：TurtleBot 4、物理 OAK-D、机器人端计算机；虚拟相机没有对应设备端推理器。
- ROS：此默认分支为 Galactic；Humble/Jazzy 兼容性 **NOT VERIFIED**。
- 复用：作为接口和流程参考；不直接运行旧跟随 launch，不照搬其运动控制或旧 DepthAI 配置。
- 借鉴：相机内部推理减少主机负荷、空间检测把 RGB 检测与深度关联起来。但简单跟随示例不是完整多人身份管理、避障和异常恢复方案。

来源：[固定版本 README](https://github.com/turtlebot/turtlebot4_examples/blob/82c8bdfedf71d5399cd3eb18d54097557551b274/README.md)。

## 3. DepthAI ROS：官方 OAK 设备端感知

- 项目：[luxonis/depthai-ros](https://github.com/luxonis/depthai-ros)，MIT。
- 版本/维护：默认 develop，`3462a2fb92fc`，最后提交 2026-11-04，近期有提交，未归档。develop 活跃不能证明其接口稳定。
- 架构：相机 pipeline、可组合 ROS 节点、标定/TF、RGBD/空间检测；ObjectTracker 可接收空间检测，保留 tracklet 的空间坐标。
- 硬件：OAK/RVC 设备及主机，原装 OAK-D Pro/Lite 属于应单独核实的设备型号；本机不存在该设备。
- ROS：官方 v3 文档明确 Humble/Jazzy 使用 `depthai_ros_driver_v3`、`ros-<distro>-depthai-ros-v3`；Kilted 及以后才把 v3 作为无后缀默认包。不能混用 v2 示例参数。
- 复用：实体 OAK-D 路线优先候选；当前纯仿真不安装设备驱动、不声称模拟 VPU 性能。
- 借鉴：把像素映射、深度 ROI、标定和时间戳保留在原始流水线；跟踪是否真正使用空间信息须看版本与配置，不能因有 XYZ 就推断关联已使用 XYZ。

来源：[v3 ROS 驱动](https://docs.luxonis.com/software-v3/depthai/ros/driver)、[ObjectTracker](https://docs.luxonis.com/software-v3/depthai/depthai-components/nodes/object_tracker)。

## 4. yolo_ros：社区 ROS 2 检测与 RGB-D 提升

- 项目：[mgonzs13/yolo_ros](https://github.com/mgonzs13/yolo_ros)。
- 版本/维护：`94d2dd500cb2`，默认 main 最后提交 2026-11-04，未归档。
- 当前源码 README 已描述 C++、ONNX Runtime 和 pluginlib 单进程流水线，包含检测、跟踪、3D 提升和调试渲染。不能再直接依赖旧版 Python/Ultralytics 节点教程。
- 硬件：RGB 或 RGB-D 输入；CPU ONNX Runtime 可运行，CUDA/TensorRT 为额外可选后端；不要求专用 OAK 设备。特定相机/主机的实测性能 **NOT VERIFIED**。
- ROS：维护者列出 Humble/Jazzy 等版本；本机实际编译及插件验证留到感知阶段。
- 许可证：核验的当前仓库为 MIT；模型权重/导出的 ONNX 不因此变成 MIT，Ultralytics 权重仍有单独条款。网上旧页面曾显示 GPL，必须按固定提交核查。
- 复用：当前纯仿真路线的重要候选，已下载固定源码，不在环境第一步提前安装整套模型/GPU依赖。
- 借鉴：模型推理后端与跟踪/深度模块分离，检测结果统一转标准接口，避免每帧图像跨多个进程重复复制。

来源：[固定版本 README](https://github.com/mgonzs13/yolo_ros/blob/94d2dd500cb26027ee9c019f4d3a02029ac615cc/README.md)、[许可证](https://github.com/mgonzs13/yolo_ros/blob/94d2dd500cb26027ee9c019f4d3a02029ac615cc/LICENSE)。

## 5. SPENCER：真实移动机器人的多模态人员跟踪

- 项目：[spencer-project/spencer_people_tracking](https://github.com/spencer-project/spencer_people_tracking)。
- 版本/维护：master `09b256ba4bc2`，默认分支最后提交 2020-09-22；仓库最近 push 为 2021-02-02，未归档，属于历史研究框架。
- 架构：RGB-D/单目/激光检测器 → 检测融合 → 人员轨迹 → 群组关系；公开基线含最近邻关联、轨迹初始化、IMM 多运动模型，不能把论文中所有高级算法都当成已公开代码。
- 实际硬件：README 记录前后 Asus Xtion Pro Live、两台 SICK LMS500，两台 i7-4700MQ/GeForce 765M 笔记本，以千兆以太网连接。这是该项目记录，不是 TurtleBot 的性能证明。
- ROS：维护者列出 ROS 1 Kinetic/Melodic/Noetic；没有据此确认 ROS 2 支持。
- 许可证：多数包 BSD，存在例外；根仓库 API 未给单一许可证，复用前逐包检查。
- 复用：不能直接安装到 Jazzy；优先借鉴消息边界、带协方差的融合、轨迹确认和群组关系，不启动移植整个老栈。

来源：[固定 README：架构与硬件](https://github.com/spencer-project/spencer_people_tracking/blob/09b256ba4bc22c5cae8a5ae88960de1a387cfd7f/README.md)。

## 6. Nav2：成熟的 ROS 2 导航与动态目标接口

- 项目：[ros-navigation/navigation2](https://github.com/ros-navigation/navigation2)。
- 维护：默认 main `3b7ec4355be9`，最后提交 2026-11-10，未归档。实际集成固定 Jazzy 分支和 apt 包版本。
- 架构：行为树管理 planner/controller/behavior server，costmap 合并激光/深度障碍物；AMCL 或 SLAM 提供定位；Collision Monitor 位于速度输出链路。
- 硬件：不绑定相机品牌，依赖配置正确的扫描/深度、里程计、TF和移动底盘；本项目使用对应虚拟传感器。
- ROS：官方 ROS 2 栈，有 Jazzy、Humble 分支。Jazzy 源码已出现 `opennav_following` 及 `FollowObject`，但是否进入当前安装二进制必须单独检查。
- 许可证：根 LICENSE 明确按包/文件分为 Apache-2.0、BSD-3-Clause、LGPL-2.1-or-later 等，不能笼统写成全部 Apache。
- 复用：是。先用 Mock Action Server，后比较动态目标行为树与专用 Following Server。后者并不自动提供完整的社会化全局绕障。
- 借鉴：目标更新通过已有导航能力完成，安全监测独立于视觉检测；不能把目标丢失时默认旋转搜索直接用于当前默认禁止运动的项目。

来源：[Jazzy 动态跟随教程](https://docs.nav2.org/jazzy/tutorials/general_tutorials/navigation2_dynamic_point_following/navigation2_dynamic_point_following/)、[Jazzy Following 包](https://github.com/ros-navigation/navigation2/blob/jazzy/nav2_following/opennav_following/package.xml)、[Collision Monitor](https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/collision_monitor/configuring_collision_monitor_node/)。

## 7—9. 追踪算法参考实现

| 项目与固定版本 | 算法与作用 | 硬件、ROS 2、维护和许可证 | 复用判断 |
|---|---|---|---|
| [ByteTrack](https://github.com/FoundationVision/ByteTrack)，`d1bf0191adff` | 高低置信度两阶段关联，结合运动预测恢复弱检测；不提供可靠跨长遮挡身份辨认 | 原始完整检测管线涉及 GPU/检测器；跟踪关联可与检测器分离。无官方 ROS 2 发行版声明。默认提交 2022-12-11，MIT，未归档 | 先做轻量基线；不把论文 V100 FPS 用于本 VM |
| [BoT-SORT](https://github.com/NirAharon/BoT-SORT)，`251985436d67` | 运动、外观、相机运动补偿与改进 Kalman 状态；ReID 需另配模型 | README 的测试系统 Ubuntu 20.04；原始实现依赖 PyTorch/相关检测器，未核实 ROS 2 支持。默认提交 2022-10-30，MIT，未归档 | 借鉴移动相机补偿和外观融合；是否降低本项目 ID switch 要实测 |
| [DeepSORT](https://github.com/nwojke/deep_sort)，`f08cf1dc470e` | Kalman、门控、匹配级联及外观嵌入；将运动与外观共同用于关联 | 原始特征提取代码含 TensorFlow，关联阶段没有摄像头绑定。无 ROS 2 发行版声明。默认提交 2025-03-02 为修正文字，不能等同于算法持续开发；GPL-3.0 | 学习关联、轨迹寿命和遮挡处理；不直接把旧 TensorFlow 栈装入 Jazzy |

论文：[ByteTrack, ECCV 2022](https://arxiv.org/abs/2110.06864)、[BoT-SORT, 2022](https://arxiv.org/abs/2206.14651)、[DeepSORT, 2017](https://arxiv.org/abs/1703.07402)。本项目没有复现这些论文的排行榜数据。

## 专业方法在本项目中的落地

1. **传感器职责**：RGB 判断类别/外观；深度给测量尺度；激光支撑障碍物和定位。不能把每个雷达障碍物都当作人，不能把单个 2D bounding box 中心的背景深度当成人体距离。
2. **融合条件**：先校验 CameraInfo、RGB-depth 对齐、曝光/仿真时间戳、TF 外参，再在共同坐标系融合。用于识别的视觉 track 与用于避障的 costmap 可以分开更新。
3. **稳定身份**：对确认轨迹使用会话级 ID，显式选择目标，保存其外观/位置及不确定度；多人交叉使用 3D 门控和外观，无法区分时停下并等待确认。
4. **遮挡与出视野**：允许短时预测，但预测不是新观测；达到超时立刻停止目标驱动，不能自动选择最近的人。绕弯时需要地图/局部避障，不能只按图像左右偏差转向。
5. **导航**：从人体位置生成有距离约束、可到达且在自由空间中的目标，目标做限频和平滑；通过 Nav2 更新目标，避免每帧取消/重建完整动作。
6. **验证**：固定场景、路径、种子、模型和权重；测墙钟延迟与仿真实时因子；把模拟真值独立于被测算法保存。现实泛化、深度孔洞和实体 VPU 性能均为 **NOT VERIFIED**。

商用项目通常还需要冗余、诊断及经过风险评估的停止链路；本次公开资料不足以断言特定厂商的内部传感器或安全等级。Collision Monitor 是软件保护组件，不替代实体机器人硬件安全。
