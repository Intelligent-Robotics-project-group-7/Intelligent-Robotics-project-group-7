# 已执行检查与测试记录

日期：2026-11-10（Europe/London）。范围：技术研究与虚拟环境第一步。

## 初始只读检查

执行：通过 `ssh -o BatchMode=yes john@192.168.48.135` 检查 `hostname`、`/etc/os-release`、`uname`、`nproc`、`free -h`、`df -h`、`lspci`、`lsusb`、ROS路径/进程/工具。

结果：SSH成功；Ubuntu26.04.1 VMware，8vCPU、7.2GiB内存、初始约15G空闲磁盘；没有ROS、OAK-D或现有TurtleBot工作空间。用户随后明确全部使用虚拟硬件。

`sudo -n true` 返回需要交互验证；rootless用户命名空间检查也未通过。没有绕过身份验证。用户在自己的SSH终端执行了已准备好的Docker安装脚本，之后新的SSH连接确认john已在docker组，Docker server/client均为29.1.3。

## 研究与下载

GitHub API核实9个项目，记录源码分支、提交日期、SHA、许可证与归档状态。成功下载TurtleBot Simulator、Nav2 Jazzy、yolo_ros固定源码；文件hash见 `../evidence/source_downloads.lock.json`。这不表示已编译yolo_ros或已测模型。

官方 `ros:jazzy-ros-base-noble` linux/amd64镜像下载压缩层合计296,615,261 bytes，离线Docker归档912,240,640 bytes。验证manifest和每层SHA-256；离线归档SHA-256为 `8411722b407e385760a6d450ef2731f29fa3b078b72501b51061c2052f89a339`。Docker load成功。

## 依赖预算与构建

执行：在基础镜像中 `apt-get update`，对Dockerfile指定包使用 `apt-get --assume-no install --no-install-recommends ...`。

结果：依赖解析成功，1个包升级、1068个新增、无需卸载；下载预算652MB，新增磁盘3269MB。`--assume-no`按预期返回1并中止安装，不能算作构建失败。之后执行 `bash scripts/build_env.sh` 安装已审核的官方仿真依赖。

构建结果：PASS。镜像`turtlebot4-research:jazzy`的ID为`sha256:40ff6b2de422b7c143d393aef97b4ec5c2b4eaccd1ac50f5d37fb9fcb4f6d11a`。安装包清单保存在`../evidence/packages.lock.tsv`。

已核实容器环境：Ubuntu24.04.5、ROS2 Jazzy、Gazebo Sim8.15.0（Harmonic）、OpenCV4.6.0、NumPy1.26.4、默认RMW为`rmw_fastrtps_cpp`。TurtleBot4 Simulator2.0.2、Description2.1.1、Create3相关包3.0.4、Nav2 1.3.13。基础与仿真包版本存在各自发行节奏，不能按一个仓库版本猜测全部包。

`ros2 doctor --report`在无外部网络的环境中无法完成部分Package/Rosdistro在线报告；这是已记录的限制，没有把整份doctor报告写成全项通过。`FollowObject`接口定义存在，但`ros2 pkg prefix opennav_following`返回未安装。

渲染核验：Xvfb虚拟显示、Mesa llvmpipe、OpenGL4.5；`Accelerated: no`。未使用硬件GPU加速或VPU。

## 静止虚拟传感器冒烟测试：PASS

最终记录时间：2026-11-10 20:46:15 UTC（当日伦敦时间相同）。观察窗口45.000秒，使用完全本地几何世界、官方TurtleBot4 standard模型，无人体资产、无检测模型。容器退出码0，9项数据链路检查全部通过。

执行命令（服务器项目目录）：

```bash
docker run --rm --init --name tb4-step1-smoke --network none --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 1024 --memory 4g --cpus 4 \
  --shm-size 512m \
  --mount type=bind,src=/home/john/projects/turtlebot4_person_following,dst=/workspace \
  turtlebot4-research:jazzy bash scripts/run_smoke.sh
```

原始记录：`../evidence/sensor_smoke.json`、`simulation.log`、`smoke_console.log`、`renderer.txt`。收到的数据如下，频率按首末接收时间估算，未包含首帧前启动等待，不是检测模型的推理FPS。

| 数据 | 实测 | 判断 |
|---|---|---|
| RGB | 715帧，320×240，rgb8，墙钟约18.07Hz | PASS：有有效图像 |
| Depth | 712帧，320×240，32FC1米制，墙钟约17.99Hz | PASS：有有效深度 |
| CameraInfo | 715条；fx≈fy≈221.765，cx160、cy120 | PASS：正内参与图像尺寸一致 |
| LaserScan | 1473条，首末接收间隔约37.43Hz | PASS：有扫描消息；未验证实体扫描频率 |
| Clock | 23570条，仿真跨度23.569秒 | PASS：仿真时钟持续推进 |
| TF | base_link到oakd_rgb_camera_optical_frame可查询 | PASS：相机到机体变换；不表示map→odom定位已完成 |
| RGB与最近Depth的stamp差 | 中位数0ms、P95为0ms | 说明该数据中存在同stamp深度；不是曝光/标定的独立验证 |
| 最后一帧深度 | 正有限值比例72.11%；中心11×11 ROI中位数2.95809m | 参考平面的一次测量；不是人物定位/深度精度实验 |

源时间推算相机频率约30.2–30.3Hz，墙钟只约18Hz；观测到的仿真时间/墙钟比例约0.58–0.60。不能把模拟时间下约30Hz写成实际实时30FPS。当前4CPU限制下的软件渲染是后续CPU推理需要考虑的预算。

运行中一次`docker stats`快照：CPU298.41%（约2.98个逻辑CPU）、内存747.5MiB、151个进程/线程、容器网络I/O为0。它不是峰值、时间平均或长时间稳定性结论。实际采样见`../evidence/smoke_resources.json`。最终宿主根盘约7.4G可用。

截图：[RGB](../evidence/camera_rgb.png)、[深度可视化](../evidence/camera_depth_0_to_5m.png)。深度颜色范围0–5m，黑色为无有效深度；画面中的几何平面不代表识别出的人。

本测试只建立传感器链路，未发布导航目标或速度命令，未加载跟随服务或Nav2；结束后临时仿真容器已停止，环境镜像与项目文件保留。URDF自带Gazebo控制硬件组件会初始化，但没有激活跟随/路径控制。

## 已遇到的问题

- 部分ROS/Nav2页面返回访问限制或旧路径404；改为官方GitHub源码、对应Jazzy文档和包清单核验，没有从不可访问页面编造结论。
- 一次SSH嵌套引号导致只读Python联网检查语法错误；后续改为上传脚本执行，GitHub下载成功。
- 构建过程中一次 `docker system df` 遇到正在变动的dpkg临时文件而失败。使用`df -h`记录真实剩余磁盘，不据此声称镜像构建失败。
- 完整官方机器人bringup触及初始512线程/进程上限，部分节点报`Resource temporarily unavailable`。静止测试改为官方模型描述、生成模型和单个传感器桥接进程，限制调整为1024，省去平台mock/运动/导航节点。
- 精简launch起初未显式传递空namespace，控制插件等待`/turtlebot4/robot_description`。传递`namespace:=''`统一命名后修复；没有改动安装的官方包。
- 官方Create3 URDF自带Sensors插件且默认ogre；无显示的初始运行失败。增加Xvfb并显式设置server渲染为ogre2。
- `xvfb-run`作为容器PID1等待就绪信号，加入Docker `--init`后解决。虚拟显示未对宿主或网络开放。
- 测试世界重复声明Sensors插件造成`Scene already exists`及Gazebo崩溃，移除项目world中的重复实例，使用官方URDF已有插件后修复。
- 首次成功采集图片后，JSON导出遇到NumPy `bool_`类型错误；显式转换内参与检查值为Python float/bool，修复后重新执行采集，避免丢失量化记录。

## 未执行项目

人体检测precision/recall、推理FPS、人体三维定位误差、多人交叉IDF1/HOTA、目标丢失恢复、Nav2跟随、停止响应、30分钟稳定性均 **NOT VERIFIED**。未发送运动指令，未启用自主跟随。

实体OAK双目精度、真实VPU性能、IR与低照度效果、实体底盘停止距离不属于本次纯虚拟测试结果。
