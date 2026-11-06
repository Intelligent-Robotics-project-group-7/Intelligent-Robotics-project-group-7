

## 几何与参考坐标

- 两轮差速驱动，前方一个球形支撑轮。
- 主体尺寸：0.56 × 0.36 × 0.16 m，主体中心相对 base_link 为 (0.08, 0, 0.18) m。
- 驱动轮半径：0.10 m，轮宽：0.06 m，轮中心间距：0.43 m。
- 含防撞条、相机凸出部分的长度约 0.66 m；两侧轮胎总宽约 0.49 m。
- base_link 位于两驱动轮接地点之间的地面投影中点；x 向前、y 向左、z 向上。
- 主体等效质量 4.0 kg；两轮各 0.25 kg、球形支撑轮 0.10 kg。
- 惯量按基本几何近似计算，主体质量包含设备外观；不是完整 CAD 装配的精确质量属性。
- 局部碰撞轮廓：x∈[-0.26,0.44]、y∈[-0.26,0.26] m，另加 0.02 m padding。
- NavFn 全局规划使用半径 0.55 m 的保守包围圆。窄门处可能拒绝真实车身能够通过的路线；之后需要按场景评估考虑完整轮廓和朝向的规划器。

## 传感器参数

| 项目 | 初始配置 | 说明 |
|---|---|---|
| LiDAR | 360°、360 点、10 Hz、0.08–12 m | 距离高斯噪声 σ=0.01 m |
| LiDAR 安装 | (0.03,0,0.48) m | 高于车轮及外观部件，待 Gazebo 再验证自身遮挡 |
| 左右相机 | 各 640×480、10 Hz、RGB、90°水平视场 | 两个独立视点，光轴平行 |
| 双目基线 B | 0.12 m | 左目 y=+0.06，右目 y=-0.06 m |
| 相机位置 | x=0.421、z=0.32 m | 视点在相机外壳前方 |
| 相机 K | fx=fy=320 px，cx=320、cy=240 px | 理想无畸变针孔参数 |
| 右目 P[3] | -38.4 | 等于 -fx×B，左目 P[3]=0 |
| IMU | 50 Hz，z 角速度噪声 σ=0.01 rad/s | 保留接口，本 PF 主实验不强制融合 IMU |
| 带噪轮式里程计 | 30 Hz，σv=0.01 m/s、σω=0.02 rad/s | 由 ROS 节点积分，并同步生成 TF |

双目不是“额外得到一张深度图”的同义词：本包提供左右彩色图像、CameraInfo 和光学 TF。
利用视差计算深度仍需 stereo_image_proc 或你们选择的匹配算法，并验证左右时间戳、CameraInfo、已知距离目标和纹理条件。
深度关系为 Z=fx×B/d，d 为左右匹配点的视差；无纹理表面不保证可靠重建。

## 话题与 TF

| ROS 话题 | 用途 |
|---|---|
| /wheel/odometry_raw | DiffDrive 原始轮式里程计，仅作诊断和噪声节点输入 |
| /wheel/odometry | 加噪速度积分得到的轮式里程计 |
| /odom | 与 /wheel/odometry 相同的消息内容，供现有导航接口使用 |
| /ground_truth/odom | Gazebo 世界真值，仅供离线评分 |
| /scan | LiDAR 扫描 |
| /imu/data | IMU |
| /stereo/left/image_raw、/stereo/right/image_raw | 左右彩色图像 |
| /stereo/left/camera_info、/stereo/right/camera_info | 左右相机内参及投影 |
| /camera/image_raw、/camera/camera_info | 同一份左目数据的接口别名，兼容原计划书 RGB 输入 |
| /cmd_vel | 给差速驱动的 Twist 指令 |

TF 链路：

```text
map → odom                    AMCL / SLAM / 自定义 PF 按模式选一个发布者
      └→ base_link            noisy_odom_node.py 发布
          ├→ laser_frame
          ├→ imu_link
          └→ stereo_camera_link
              ├→ left_camera_link → left_camera_optical_frame
              └→ right_camera_link → right_camera_optical_frame
```

相机机体坐标 x前/y左/z上；光学坐标 x右/y下/z前。启动文件已经给出对应旋转。
不再启动旧大车的 base_link→laser_frame 静态发布器，否则安装参数会冲突。

## 带噪里程计的含义

```text
DiffDrive 原始轮速里程计
       ↓
给 v 和 ω 加独立高斯测量噪声与可配置固定偏置
       ↓
按消息时间戳进行圆弧积分
       ↓
/odom、/wheel/odometry 与 odom→base_link TF
```

这次位姿和 TF 都由含噪速度积分产生，因此确实会累积误差。
不能只给 twist 加噪、却继续把原始理想 pose 或 TF 交给导航，然后把它当作有漂移的里程计基线。
原始 Gazebo TF 没有桥接；真值插件的 gaussian_noise 保持 0，也没有把真值 TF 桥接到 /tf。
协方差由一阶线性化传播，未包括未建模的打滑、接触误差等；它不是完整硬件不确定性的标定值。
seed=42 只固定该节点的随机抽样序列。丢帧、起始时刻、轨迹和 Gazebo 的 LiDAR 随机源仍影响整场实验可重复性。



## 第一阶段：只看外观和运动稳定性

```bash
source /opt/ros/jazzy/setup.bash
cd "$HOME/Documents/Intelligent Robot/rob_ws"
ros2 launch "$PWD/src/learning_pkg_python/launch/rescue_platform.launch.py" start_bridge:=false
```
这会加载新 Gazebo 场景，先观察：落地后是否稳定、车轮是否正确接地、外壳是否穿插、传感器是否被遮挡。
PNG 预览是根据 SDF 几何生成的设计示意，不是这一阶段已通过的运行证据。

## 第二阶段：启动传感器与里程计接口

结束第一阶段的启动程序，在同一终端运行：

```bash
ros2 launch "$PWD/src/learning_pkg_python/launch/rescue_platform.launch.py"
```

这一条启动 Gazebo、桥接、带噪里程计和全部传感器静态 TF。软件渲染默认开启；原生 GPU 可用时可按需传 software_rendering:=0。
它不启动定位、SLAM 或导航。不要再单独运行旧桥接、旧 wheel_noise 或旧静态 TF。

建议依次检查：

```bash
ros2 topic echo /odom --once
ros2 run tf2_ros tf2_echo base_link laser_frame --ros-args -p use_sim_time:=true
ros2 topic echo /scan --field ranges --once --qos-reliability best_effort
ros2 topic echo /stereo/left/camera_info --once --qos-reliability best_effort
ros2 topic echo /stereo/right/camera_info --once --qos-reliability best_effort
ros2 topic echo /stereo/left/image_raw --field header --once --qos-reliability best_effort
ros2 topic echo /stereo/right/image_raw --field header --once --qos-reliability best_effort
```

右目 CameraInfo 的 P 数组第 4 项应为 -38.4，左目为 0；左右图像 header 应对应各自 optical_frame。
需要同时取样/录包比较左右图像时间戳，不能拿两条隔了几秒执行的 --once 命令判断同步情况。
三个传感器更新频率和相机分辨率是起始值，实际负载需要在虚拟机中测量。改变双目分辨率/视场时，两目 K、P 必须配套更新。


