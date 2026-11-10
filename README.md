# TurtleBot 4 人体检测与跟随研发：第一步

日期：2026-11-10。当前范围：成熟方案调研、技术选型、隔离开发环境、静止虚拟传感器验证。所有硬件按用户要求为虚拟硬件。

服务器项目：`/home/john/projects/turtlebot4_person_following`

第一步已完成：9个开源项目调研、6份文档、隔离环境构建，以及45秒静止虚拟传感器检查（9项通过）。实际图像320×240，首末接收间隔约18Hz；仿真约0.6倍实时。人体识别与跟随尚未实现/测试。

## 阅读入口

- [行业与9个开源项目调研](docs/industry_research.md)
- [技术比较与选型](docs/technology_comparison.md)
- [系统架构设计稿](docs/system_architecture.md)
- [虚拟硬件资源评估](docs/hardware_assessment.md)
- [分阶段计划和量化验收建议](docs/implementation_plan.md)
- [真实执行记录](docs/test_report.md)

## 环境

Ubuntu 26.04宿主安装Docker，容器内使用Ubuntu24.04、ROS2 Jazzy和Gazebo Harmonic。固定基础镜像digest在Dockerfile和 `evidence/ros_image.lock.json`；固定源码与sha256见 `evidence/source_downloads.lock.json`。版本列表和执行结果以 `docs/test_report.md` 为准。

基础镜像离线归档已保存在服务器 `downloads/ros-jazzy-ros-base-noble.tar`。这不是包含全部仿真软件的最终镜像；最终环境由Dockerfile构建。源码压缩包只是参考/后续开发材料，下载不等于已经编译集成。

## 服务器命令

```bash
cd /home/john/projects/turtlebot4_person_following
# 第一次已经完成的宿主安装：sudo bash scripts/bootstrap_host.sh

# 重建环境（会访问Ubuntu/ROS仓库；不是时间快照）
bash scripts/build_env.sh

# 交互式进入隔离环境
bash scripts/run_env.sh bash

# 容器内静止相机检查，无人体检测或运动命令
bash scripts/run_env.sh bash scripts/run_smoke.sh
```

运行脚本默认无外部网络、不映射实体设备、去除capabilities、设置CPU/内存限制。静止测试使用完全本地的几何世界与官方机器人模型；几何参考物不代表识别出来的人物。Nav2、SLAM、自动跟随均不由该测试激活。

下一阶段在相机链路验证后，才引入人体资产/模型与独立真值进行检测、深度定位和多人跟踪实验。实体OAK深度精度/VPU性能以及真实底盘跟随效果均为 **NOT VERIFIED**。
