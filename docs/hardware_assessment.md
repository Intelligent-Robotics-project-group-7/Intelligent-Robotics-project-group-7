# 当前虚拟硬件与计算资源评估

日期：2026-11-10。用户明确：全部是虚拟硬件。

## 实际只读检查

SSH：`john@192.168.48.135`，主机名 `john-VMware-Virtual-Platform`。

| 项目 | 已观察结果 | 对工程的影响 |
|---|---|---|
| 系统 | Ubuntu 26.04.1 LTS，x86_64，VMware | 使用Ubuntu24.04容器运行官方Jazzy组合 |
| CPU | 8 vCPU，暴露型号 i7-13650HX | 可进行CPU推理和软件渲染；不是独占物理核心性能保证 |
| RAM | 约7.2 GiB，初检可用5.2 GiB；swap4GiB | 仿真初始上限4GiB/4CPU，给宿主与已有服务留资源 |
| 磁盘 | 根盘30G，初检约15G空闲 | 只装单套环境，不下载大型训练集/多套GPU框架 |
| 图形 | VMware SVGA II；有 /dev/dri | 不等于CUDA GPU直通。先使用Mesa软件渲染 |
| USB | VMware鼠标/集线器及root hub | 没有可见OAK-D；实体相机型号/标定/USB速率 NOT VERIFIED |
| ROS/源码 | 初检无 /opt/ros、ros2、Docker与TurtleBot工作空间 | 允许新建隔离研发目录，不改已有其他项目 |
| 实体底盘/雷达 | 不适用，本项目虚拟硬件 | 不声称实测Create3固件或真实RPLIDAR能力 |

命令与后续安装结果见 `test_report.md` 及 evidence。Gazebo 中的相机和雷达型号是选用模型的配置，不是现场盘点出的真实设备。

## 计算架构比较

| 方案 | 性能与延迟 | 电源/散热、USB/网络 | 驱动/复杂度 | 成本与当前决定 |
|---|---|---|---|---|
| A：原装OAK推理+Pi运行ROS | 可把推理下放到VPU；全链路FPS/深度精度 NOT VERIFIED | 实体需要核实USB3、供电和散热；发布检测比传全RGBD省带宽 | 必须匹配RVC/DepthAI/ROS版本 | 如果已有实物可优先复用；当前无实体设备，不能实验此方案 |
| B：外部Ubuntu计算机 | 可选CPU/GPU；网络、队列和编解码增加延迟 | 传RGBD需带宽预算与时钟同步 | 机器人驱动保持本地，主机感知经标准接口接入 | 当前使用VM模拟同类分工，额外软件许可费用0；硬件采购不需要 |
| C：Jetson边缘计算 | 具有支持模型的GPU加速潜力；不是TOPS到FPS的直接换算 | 电源转换、散热、负载和安装位置需要实测 | JetPack/ROS/Isaac版本强耦合 | 当前不建议购买；2024年官方发布价$249只是历史参考，2026当地含税总价 NOT VERIFIED |
| D：更换/增加传感器 | 广视角可能缓解出视野，其他深度技术各有失败模式 | 增加USB/网络/电源、外参标定负担 | 多源同步、融合和故障诊断更复杂 | 当前没有必要；具体型号/价格 NOT VERIFIED，先量化既有模型瓶颈 |

Jetson价格来源：[NVIDIA 2024-12-17公告](https://developer.nvidia.com/blog/nvidia-jetson-orin-nano-developer-kit-gets-a-super-boost)。它不是当前可购买报价。Isaac ROS支持限制见[版本4.0平台表](https://nvidia-isaac-ros.github.io/v/release-4.0/repositories_and_packages/isaac_ros_dnn_inference/index.html)。

## 传输与实时性预算

计算示例，**不是测量值**：640×480 RGB8、30Hz 的原始有效载荷约27.65MB/s；同尺寸32FC1深度约36.86MB/s，合计约64.51MB/s（516Mb/s），尚未加DDS、IP、点云或重传开销。因此当前把仿真和处理放在同一容器，先不额外发布高密度点云。

记录实际图像尺寸/编码/频率；CPU推理前可降低模型输入尺寸，但应保留从模型像素到原RGB/深度像素的映射。图像缩放或压缩不应破坏CameraInfo对应关系。

## 仿真能够与不能验证的内容

可以验证：接口、TF、同步、深度单位、位置计算、目标状态机、导航调用、传感器超时、CPU资源和仿真时间行为。

**NOT VERIFIED**：实际OAK双目测距误差、低照度/IR效果、透明反光物体、真实曝光运动模糊、USB掉线特征、真实VPU推理吞吐、实体底盘停止距离和人群安全。

第一步不升级硬件。若软件渲染实时因子低，先降低虚拟分辨率/帧率和世界复杂度，或申请更多VM资源；只有定位到明确计算瓶颈后再考虑GPU直通或独立Ubuntu环境。
