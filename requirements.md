# TurtleBot 4 专业机器人研发与技术选型任务

## 你的角色

你现在是一支专业的机器人研发团队，需要同时具备以下角色的能力：

1. Robotics Systems Engineer（机器人系统工程师）
2. Computer Vision Engineer（计算机视觉工程师）
3. ROS 2 Software Engineer（机器人软件工程师）
4. Robotics Perception Engineer（机器人感知工程师）
5. Embedded AI Engineer（嵌入式 AI 工程师）
6. Robotics Test Engineer（机器人测试工程师）

不要仅仅像普通程序员一样编写 YOLO 示例代码。

你的首要任务是研究专业机器人研发团队如何设计和实现“人体检测、人体定位、人体跟踪、自主跟随”系统，再基于我的 TurtleBot 4 进行工程实现。

**核心原则：先研究和理解专业方法，再选择技术，最后编写和测试代码。**

---

## 一、研究专业机器人行业的技术方案

请通过官方文档、GitHub 开源项目、科研论文、ROS 社区和真实机器人项目进行调研。

重点研究：

- 研究型移动机器人怎样检测和跟踪行人？
- 商用服务机器人通常采用什么传感器组合？
- 专业团队如何融合 RGB 摄像头、深度摄像头和激光雷达？
- 为什么某些项目使用 YOLO，另一些使用 DepthAI 或其他检测框架？
- 人体跟随应该采用 Nav2 动态导航目标、局部控制器还是其他方法？
- 多人场景中如何持续跟踪指定人员？
- 人被遮挡、转弯、走出摄像头视野时如何处理？
- 如何保证机器人在人员附近运行的安全性？

请至少研究 5 个相关、真实存在的开源项目或技术实现。

每个项目需要记录：

- 项目名称和 GitHub URL
- 主要功能
- 软件和算法架构
- 使用的摄像头、雷达和计算硬件
- 支持的 ROS 2 版本
- 维护状态与许可证
- 是否能够直接复用于 TurtleBot 4
- 有哪些技术值得借鉴

**不要编造项目、性能指标、硬件兼容性或测试结果。**

优先使用官方技术文档、源码和真实测试数据。区分“官方支持”“社区实现”和“未经验证的设想”。

## 二、研究专业软件和算法框架

系统性比较以下技术。

### 机器人核心框架

- ROS 2 Humble / Jazzy
- TF2
- DDS
- Nav2
- SLAM Toolbox
- AMCL
- ROS 2 Lifecycle Nodes
- ROS 2 Actions、Services、Topics

解释它们的职责，以及哪些组件应该使用、哪些不需要。

### 视觉与人体检测

- OpenCV
- Ultralytics YOLO
- DepthAI
- SpatialDetectionNetwork
- RGB-D 人体三维定位
- MediaPipe
- 其他具有实际工程价值的方案

重点比较：

1. 检测准确率
2. 推理速度
3. 深度信息集成方式
4. CPU、GPU、VPU 占用
5. ROS 2 集成难度
6. 对 TurtleBot 4 原装 OAK-D 的适配程度

不要默认 YOLO 一定是最好的方案。

### 多目标跟踪

研究：

- ByteTrack
- DeepSORT
- BoT-SORT
- Kalman Filter
- DepthAI ObjectTracker
- 三维目标数据关联

需要解释：

- 如何维持稳定的 Track ID
- 如何锁定一个指定目标
- 如何避免在多人交叉时跟错人
- 如何处理临时遮挡
- 目标重新出现后如何恢复跟踪
- 什么情况下应该停止而不是重新选择目标

### 机器人导航与运动

研究：

- Nav2
- Costmap 2D
- MPPI Controller
- Regulated Pure Pursuit
- Dynamic Goal Updating
- Collision Monitor
- 动态障碍物处理
- 社会化导航（Social Navigation）

特别比较两种跟随模式：

A. 使用 Nav2 持续更新跟随目标点。

B. 使用独立的闭环人体跟随控制器，同时保留避障与安全控制。

解释各自的优势、局限和适用环境，提出适合 TurtleBot 4 的选择。

## 三、研究专业硬件架构

首先检查当前 TurtleBot 4 的实际硬件和驱动，不能只根据型号猜测。

现有基础硬件可能包括：

- Raspberry Pi 4
- OAK-D Pro 或 OAK-D Lite
- RPLIDAR A1
- iRobot Create 3 底盘

研究以下计算架构：

**方案 A：完全使用原装硬件**

OAK-D 负责 AI 推理，Raspberry Pi 运行 ROS 2，雷达辅助导航。

**方案 B：机器人 + 外部 Ubuntu 电脑**

机器人负责传感器采集和运动，外部电脑负责 AI 推理、目标跟踪及必要的导航计算。

**方案 C：增加边缘 AI 计算设备**

研究 NVIDIA Jetson 等硬件及相关加速框架。

**方案 D：更换或增加传感器**

仅在有明确技术理由时，比较其他深度摄像头、广角摄像头或雷达。

针对各方案输出比较表：

- 计算性能
- 延迟与实时性
- 供电和散热
- USB、网络和带宽要求
- 驱动兼容性
- 系统复杂度
- 估计成本及来源
- 是否值得升级

优先复用 TurtleBot 4 原装硬件，不要未经验证就推荐购买新设备。

## 四、调研专业团队常用的开发工具

研究并选择适合这个项目的工具链：

- Ubuntu + ROS 2
- VS Code / Codex
- Git / GitHub
- colcon / CMake
- Python / C++
- RViz2
- Gazebo
- Foxglove
- PlotJuggler
- rosbag2
- OpenCV
- pytest / launch_testing
- Docker / Dev Container

对每种工具说明用途，并区分：

- 必须安装
- 推荐安装
- 可选工具
- 当前项目不需要

制定一个尽可能轻量、可复现、容易维护的开发环境。

## 五、研究并设计完整系统架构

基于调研结果，提出推荐架构：

Camera → Person Detection → Depth Estimation → Tracking → Target Selection → TF2 → Motion Planning → Nav2 → Robot

请具体定义：

1. ROS 2 节点划分
2. Topics、Messages、Actions、Services
3. CameraInfo 与 RGB/Depth 对齐
4. 图像时间同步
5. Camera、base_link、odom、map 坐标变换
6. 检测与跟踪数据结构
7. 目标位置滤波和预测
8. 动态导航目标生成
9. Nav2 与避障系统集成
10. 目标丢失后的安全处理
11. 生命周期与异常恢复
12. 日志、监控与测试接口

优先采用已有标准消息类型和成熟组件，避免重复造轮子。

提供 ROS 2 节点关系图、数据流图、推荐目录结构和软件模块边界。

## 六、对比两条主要实现路线

### 路线 A：DepthAI 原生 AI 方案

利用 OAK-D 摄像头内部的 AI 推理和深度能力。

研究是否能够在当前相机、固件和驱动条件下使用：

- 人体检测神经网络
- Spatial Detection
- ObjectTracker
- 三维坐标输出
- ROS 2 消息发布

特别检查 DepthAI v2 与 v3、ROS 2 Humble/Jazzy 驱动的兼容关系。

不得直接使用不匹配版本的示例配置。

### 路线 B：ROS 2 + YOLO 方案

通过 ROS 2 获取 RGBD 数据，在外部计算设备运行人体检测模型，再完成深度定位和目标跟踪。

研究模型、推理后端、时间同步、坐标系统、数据传输延迟等问题。

对两条路线进行实验比较，并给出推荐结论。

不要只根据理论 FPS 选择方案。需要考虑全链路延迟、深度精度、跟踪稳定性和维护成本。

## 七、检查当前工作空间

调研完成后，检查本地环境：

- 操作系统
- ROS 2 发行版
- TurtleBot 4 型号
- DepthAI 驱动版本
- 已安装的 ROS 2 包
- 实际运行节点
- RGB、Depth、CameraInfo、LaserScan、TF 话题
- 已有源代码和配置
- Nav2 状态
- GPU / CPU / RAM 资源
- 可用的 rosbag 数据

先只读检查，不要立即修改系统配置。

检查是否有可以直接复用的功能。

若真实硬件不可访问，明确标记，并使用模拟数据或 rosbag 继续开展能够验证的工作。

## 八、制定专业的测试与性能评估方法

至少包含以下测试：

### 感知测试

- 人体检测成功率
- 检测 FPS
- 端到端感知延迟
- 误检和漏检
- 深度测距误差
- RGBD 同步误差
- 不同距离下的测量稳定性

### 跟踪测试

- Track ID 持续性
- 多人交叉
- 临时遮挡
- 目标离开视野
- 目标重新进入视野
- 错误目标切换率

### 导航测试

- 跟随距离误差
- 跟随路径平滑程度
- 转弯性能
- 停止响应时间
- 障碍物绕行
- 定位丢失后的处理
- 通信中断后的行为

### 性能测试

- CPU 使用率
- GPU / VPU 使用情况
- 内存占用
- ROS 2 通信延迟
- 网络带宽
- 长时间稳定性

需要提出合理的量化验收指标，并说明指标依据。

不能把未经测试的预期值写成实际结果。

## 九、开发和安全要求

先研究，再选择实现路线，再逐步开发。

执行顺序：

1. 专业技术调研
2. 技术比较和方案选择
3. 系统架构设计
4. 原装摄像头测试
5. 人体检测
6. 深度定位
7. 目标跟踪
8. ROS 2 节点集成
9. rosbag 与仿真测试
10. Nav2 逻辑验证
11. 真实机器人低速测试准备

安全约束：

- 默认禁止机器人自主移动。
- 不得自动启用跟随服务。
- 不得在未经明确授权时发送真实运动指令。
- 先使用仿真或 Mock Action Server 验证导航逻辑。
- 研究急停、速度限制、传感器超时和碰撞监测机制。
- 软件 Collision Monitor 不能代替硬件级安全保障。
- 未经确认，不得替换原装驱动或破坏现有配置。
- 需要实际运动测试时，明确列出前置检查，等待我单独授权。

## 十、必须交付的文件

请在工作空间中创建并维护以下文档：

`docs/industry_research.md`

专业机器人行业的技术与开源项目调研报告，带来源链接、版本和研究日期。

`docs/technology_comparison.md`

软件、算法框架和硬件方案对比，包括选型依据。

`docs/system_architecture.md`

推荐系统架构、ROS 2 节点图、接口、TF、导航方案。

`docs/hardware_assessment.md`

TurtleBot 4 现有硬件评估和是否需要升级的建议。

`docs/implementation_plan.md`

分阶段开发任务、依赖关系、风险、验收标准。

`docs/test_report.md`

真实执行过的检查与测试，记录命令、结果、错误和性能指标。

请把无法验证的内容清楚标注为 NOT VERIFIED，不允许猜测。

## 十一、参考资料

从以下官方资源开始研究，并进一步查找相关专业项目：

TurtleBot 4 User Manual:
https://turtlebot.github.io/turtlebot4-user-manual/

TurtleBot 4 GitHub:
https://github.com/turtlebot

Luxonis DepthAI:
https://docs.luxonis.com/

DepthAI ROS:
https://github.com/luxonis/depthai-ros

ROS 2:
https://docs.ros.org/

Nav2:
https://docs.nav2.org/

NVIDIA Isaac ROS:
https://developer.nvidia.com/isaac/ros

如果网络访问不可用，说明哪些技术无法核实，不要虚构调研结果。

## 最终目标

不要只完成一个能够在画面中画出人体框的 Demo。

我要的是一个按照专业机器人研发方法设计的 TurtleBot 4 人体检测与自主跟随项目，具有：

- 可维护的软件架构
- 可复现的开发环境
- 稳定的人体检测和三维定位
- 可靠的目标跟踪
- 可测试的导航算法
- 明确的安全保护机制
- 可量化的性能指标
- 可继续扩展的工程基础

现在开始执行。

**第一优先级：研究专业机器人团队现有的成熟技术和开源实现。**

然后给出专业技术选型结论，尽可能直接完成当前环境允许的只读检查、文档编写和离线测试。

不要未经验证就安装大量依赖，也不要把未经测试的系统描述为已经完成。