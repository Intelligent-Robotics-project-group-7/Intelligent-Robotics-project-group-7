# TurtleBot 4 人体检测与跟随研发

日期：2026-11-10。已完成技术调研、隔离仿真环境和第二阶段二维人物检测基线。所有硬件按用户要求为虚拟硬件。

服务器项目：`/home/john/projects/turtlebot4_person_following`

第一步：9个开源项目调研、环境构建和传感器9项检查通过。第二步：C++/ONNX CPU检测、标准ROS消息、独立真值与六场景360帧评估完成。总体召回78.26%；近距单人100%，两人交叉68.33%，遮挡40.91%。三维定位、身份跟踪和自主跟随尚未完成。

## 阅读入口

- [第二阶段检测结果、失败样本与复现方法](docs/phase2_detection.md)
- [行业与9个开源项目调研](docs/industry_research.md)
- [技术比较与选型](docs/technology_comparison.md)
- [系统架构设计稿](docs/system_architecture.md)
- [虚拟硬件资源评估](docs/hardware_assessment.md)
- [分阶段计划和量化验收建议](docs/implementation_plan.md)
- [真实执行记录](docs/test_report.md)

## 环境

Ubuntu 26.04宿主安装Docker，容器内使用Ubuntu24.04、ROS2 Jazzy和Gazebo Harmonic。固定基础镜像digest在Dockerfile和 `evidence/ros_image.lock.json`；固定源码与sha256见 `evidence/source_downloads.lock.json`。版本列表和执行结果以 `docs/test_report.md` 为准。

基础镜像离线归档保存在服务器 `downloads/ros-jazzy-ros-base-noble.tar`；仿真环境由Dockerfile构建。第二阶段已编译yolo_ros overlay；第一阶段下载的Nav2源码仍作为参考，没有替换apt安装版本。

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

第二阶段复用同一镜像，在`research_ws/`构建固定提交的yolo_ros 5.0.0与ONNX Runtime 1.20.0。输入来源与hash见`config/phase2_assets.lock.json`；大型输入与编译结果不进入Git。Ubuntu服务器命令：

```bash
bash scripts/setup_perception.sh
bash scripts/run_person_suite.sh
bash scripts/analyze_person_suite.sh
```

![人物检测示例](evidence/phase2/detection_contact_sheet.png)

人物网格来源OpenRobotics Scrubs，CC BY 4.0，详见第二阶段报告。绿色检测框、蓝色独立真值框；交叉与遮挡存在明显漏检。下一阶段是深度定位，保留困难案例回归。实体OAK深度精度/VPU性能以及真实底盘跟随效果均为 **NOT VERIFIED**。
