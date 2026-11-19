# TurtleBot 4 搜救路径规划与导航 / Search and Rescue Navigation

**负责人 / Owner:** Ge Mei

**交付内容 / Deliverable:** [`meg_navigation/`](./) — ROS 2 Jazzy 导航包 / ROS 2 Jazzy navigation package

本包在未知室内平面环境中选择探索目标、检查路径可达性、调用 Nav2 导航、接近已报告的人员位置，并在记录完成后返回出发点。人员识别、相机坐标计算、建图节点和仿真世界由其他模块提供。

This package selects exploration goals in an initially unknown, flat indoor environment, checks route reachability, sends goals to Nav2, approaches a reported person location, and returns to the start after recording is confirmed. Person detection, camera-coordinate calculation, SLAM, and the simulation world are supplied by other modules.

> **当前状态 / Current status:** 栅格算法单元测试通过；二维测试场景完成过探索、模拟目标接近和返程；三维 Gazebo 场景仅验证到自主探索目标。双目视觉到地图坐标的接口和完整三维搜救流程尚未联调。 / Grid-planning unit tests pass; 2D test scenes have completed exploration, simulated-target approach, and return; the 3D Gazebo trial reached an autonomous exploration goal only. Stereo-to-map integration and the complete 3D rescue mission remain untested.

## 1. 模块与文件 / Components and files

| 文件 / File | 作用 / Purpose |
| --- | --- |
| [`grid.py`](meg_navigation/grid.py) | 占据栅格上的 A* 可达性检查、探索前沿选择、目标附近安全接近位姿选择。 / A* reachability checks, frontier selection, and safe approach-pose selection on an occupancy grid. |
| [`mission.py`](meg_navigation/mission.py) | 管理任务状态，接收地图、人员坐标和记录确认，向 Nav2 发送探索、接近及返程目标。 / Manages mission state; receives map, target and recording acknowledgement; sends exploration, approach and return goals to Nav2. |
| [`nav2_tb4_astar.yaml`](config/nav2_tb4_astar.yaml) | TurtleBot 4 Nav2 参数；全局规划器设置为 `SmacPlanner2D`（A*）。 / TurtleBot 4 Nav2 parameters; sets `SmacPlanner2D` (A*) as the global planner. |
| [`navigation.launch.py`](launch/navigation.launch.py) | 启动 TurtleBot 4 Nav2 和本包任务节点。 / Starts TurtleBot 4 Nav2 and this package's mission node. |
| [`test_grid.py`](test/test_grid.py) | 栅格路径、探索点和接近位姿的单元测试。 / Unit tests for grid routes, frontiers, and approach poses. |

`grid.py` 中的 A* 用于筛选候选目标。小车实际行驶的全局路径由 Nav2 的 `SmacPlanner2D` 计算；Nav2 控制器处理局部避障和速度指令。本包不直接发布 `/cmd_vel`。

A* in `grid.py` filters candidate goals. Nav2's `SmacPlanner2D` computes the global path used by the robot; the Nav2 controller handles local obstacle response and velocity commands. This package does not publish `/cmd_vel` directly.

## 2. 任务流程 / Mission workflow

1. **准备 / Initialise:** 等待有效 `/map`、已激活的 Nav2 和机器人地图位姿；若 `/dock_status` 报告仍在充电座上，先调用离座动作，再记录返程位姿。 / Wait for a usable `/map`, active Nav2, and the robot pose in `map`; if `/dock_status` reports docking, call the undock action, then record the return pose.
2. **探索 / Explore:** 在没有人员目标时，从已知空闲区域与未知区域交界处选取可达探索点；本包做 A* 可达性检查，并把目标交给 Nav2。 / With no person target, choose reachable frontiers between known free and unknown space, check reachability with A*, and pass goals to Nav2.
3. **接近 / Approach:** 收到地图坐标系中的 `/rescue_target` 后，选择目标附近安全且可达的停靠位姿；如果周围地图尚不足以规划，则继续探索。默认停靠距离约为 `0.8 m`。 / After receiving `/rescue_target` in `map`, select a safe, reachable stopping pose near the target. Continue exploring if the surrounding map is insufficient. The default stopping distance is about `0.8 m`.
4. **确认与返程 / Confirm and return:** 默认等待 `/rescue_recorded=true`，然后返回所记录的起点。返回成功发布 `DONE`；任务终止失败发布 `FAILED` 及原因。 / By default, wait for `/rescue_recorded=true`, then navigate to the recorded start pose. Publish `DONE` after a successful return, or `FAILED` with the reason on terminal failure.

每次任务只接受第一个有效人员目标；后续目标更新会被忽略。探索目标由本包生成，感知模块无需持续提供中间导航点。

Each mission accepts only the first valid person target; later target updates are ignored. This package generates exploration goals, so perception does not need to send intermediate waypoints.

## 3. ROS 2 接口约定 / ROS 2 interface contract

| 方向 / Direction | 名称 / Name | 类型 / Type | 提供方与要求 / Provider and requirement |
| --- | --- | --- | --- |
| 输入 / Input | `/map` | `nav_msgs/msg/OccupancyGrid` | 建图模块持续发布二维占据地图。 / Mapping publishes an updated 2D occupancy grid. |
| 输入 / Input | TF `map → base_link` | TF transform | 定位或 SLAM 提供机器人在地图中的位姿。 / Localisation or SLAM provides the robot pose in the map frame. |
| 输入 / Input | `/dock_status` | `irobot_create_msgs/msg/DockStatus` | TurtleBot 4 报告是否在充电座上；默认必须提供。 / TurtleBot 4 reports docking state; required by default. |
| 输入 / Input | `/rescue_target` | `geometry_msgs/msg/PointStamped` | 感知集成端发布人员位置；`header.frame_id` 必须为 `map`，`point.x/y` 必须是有限数值。 / The perception integration publishes a person location; `header.frame_id` must be `map`, and `point.x/y` must be finite. |
| 输入 / Input | `/rescue_recorded` | `std_msgs/msg/Bool` | 记录模块保存信息后发布 `true`；默认收到确认才返程。 / Recording publishes `true` after saving information; required before return by default. |
| 输出 / Output | `/meg_navigation/status` | `std_msgs/msg/String` | 状态文本，终态以 `DONE:` 或 `FAILED:` 开头。 / Status text; terminal states begin with `DONE:` or `FAILED:`. |
| 动作客户端 / Action client | `navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | 向 Nav2 发送探索、接近和返程位姿。 / Sends exploration, approach, and return poses to Nav2. |
| 动作客户端 / Action client | `undock` | `irobot_create_msgs/action/Undock` | 小车处于充电座时请求离座。 / Requests undocking when the robot is docked. |

**视觉模块接入点 / Perception integration point:** 队友当前的视觉 README 描述 `/perception/people/center_poses` 为 `geometry_msgs/msg/PoseArray`，使用假定的 `assumed_robot` 坐标系；其中未应用机器人定位、TF 或相机安装偏移。该消息不能直接作为 `/rescue_target` 使用。联调时需要选定有效人员目标，结合真实相机标定和机器人 TF 转换到 `map`，再发布 `PointStamped`。这段适配尚未在本包中实现或验证。

The teammate's current vision README describes `/perception/people/center_poses` as `geometry_msgs/msg/PoseArray` in an assumed `assumed_robot` frame; robot localisation, TF, and camera mounting offset are not applied. That message cannot be used directly as `/rescue_target`. Integration must select a valid person target, transform it to `map` using calibrated camera geometry and robot TF, and publish a `PointStamped`. This adapter has not been implemented or verified in this package.

## 4. 环境与构建 / Environment and build

已使用的开发环境为 Ubuntu、ROS 2 Jazzy、Gazebo Harmonic 和 TurtleBot 4 Lite 仿真。运行前还需要 TurtleBot 4 Navigation、Nav2、机器人仿真或实体底盘、建图/定位及上述输入接口；这些系统不包含在本交付包中。依赖声明见 [`package.xml`](package.xml)。

The development setup used Ubuntu, ROS 2 Jazzy, Gazebo Harmonic, and a simulated TurtleBot 4 Lite. Runtime also needs TurtleBot 4 Navigation, Nav2, the robot simulation or hardware stack, mapping/localisation, and the input interfaces above; these are not included in this deliverable. Package dependencies are declared in [`package.xml`](package.xml).

从主分支克隆小组仓库，然后在仓库根目录构建 `scr/meg_navigation/`。若仓库需要认证，请使用有权限的 GitHub 账号。

From a fresh checkout of the team repository, build `scr/meg_navigation/` from the repository root. Authenticate with a GitHub account that has repository access if required.

```bash
git clone --branch main --single-branch \
  https://github.com/Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7.git meg-nav
cd meg-nav
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths scr/meg_navigation --ignore-src --rosdistro jazzy -r -y
colcon build --symlink-install --base-paths scr/meg_navigation --packages-select meg_navigation
source install/setup.bash
```

`rosdep` 需要已配置的软件源及安装权限。构建成功仅证明包可安装；完整任务还依赖仿真、地图、TF、感知和记录模块。

`rosdep` requires configured package sources and installation privileges. A successful build only establishes that the package can be installed; the complete mission also depends on simulation, map, TF, perception, and recording components.

## 5. 启动与检查 / Launch and checks

先启动机器人仿真或实体底盘与建图/定位，确保 `/map` 和 `map → base_link` 可用。随后在已执行 `source install/setup.bash` 的终端启动本包。此 launch 会启动 Nav2，避免同时运行第二套 Nav2 或重复发布 `map → odom`。

Start the robot simulation or hardware stack and mapping/localisation first; confirm `/map` and `map → base_link` are available. Then launch this package in a terminal where `install/setup.bash` has been sourced. This launch starts Nav2; avoid a second Nav2 stack or duplicate `map → odom` publishers.

```bash
ros2 launch meg_navigation navigation.launch.py
```

默认使用仿真时钟，并要求记录确认。`start_mission:=false` 仅启动 Nav2；`use_sim_time:=false` 可用于实体机器人，但实体部署尚未验证。仅在隔离导航测试中可用 `require_recording_ack:=false` 跳过记录确认；这不代表记录功能已联调。

Defaults use simulation time and require recording acknowledgement. `start_mission:=false` starts Nav2 only. `use_sim_time:=false` is available for hardware, but hardware deployment has not been verified. `require_recording_ack:=false` can bypass recording for an isolated navigation test; it does not verify recording integration.

```bash
# 在另一个已加载 ROS 环境的终端检查 / Check in another ROS-sourced terminal
ros2 topic echo /meg_navigation/status
ros2 topic info /map
ros2 run tf2_ros tf2_echo map base_link
```

有地图和 TF 后，状态应从准备阶段进入探索阶段。收到有效目标并完成记录确认后，只有成功返程才会看到 `DONE:`。`FAILED:` 表示任务失败，后面的文字给出原因。若始终停在准备阶段，先检查地图、Nav2 激活状态、充电座状态和 TF。

With map and TF available, status should advance from readiness into exploration. After a valid target and recording acknowledgement, `DONE:` appears only after a successful return. `FAILED:` indicates failure and includes a reason. If the mission remains in readiness, check the map, Nav2 activation, dock status, and TF first.

## 6. 已完成的验证 / Completed verification

| 场景 / Scenario | 实测结果 / Observed result | 范围 / Boundary |
| --- | --- | --- |
| 栅格算法单元测试 / Grid algorithm unit tests | 7 个测试通过。 / 7 tests passed. | 检查 A*、探索点和接近点选择；不驱动机器人。 / Checks A*, frontier and approach selection; does not drive a robot. |
| 未知二维门洞及绕墙场景 / Unknown 2D doorway and detour scenes | 探索、模拟人员目标接近及返程到达 `DONE`。 / Exploration, simulated-target approach, and return reached `DONE`. | 目标由测试程序提供，记录确认被关闭；未测试双目识别。 / Target came from a test fixture; recording acknowledgement was disabled; stereo detection was not tested. |
| 二维双隔墙场景 / 2D two-partition scene | 一次运行中接近成功，返程失败。 / In one run, approach succeeded and return failed. | 复杂地图的返程可靠性仍需改善。 / Return reliability in harder maps still needs work. |
| 三维 Gazebo 简单房间 / Simple 3D Gazebo room | TurtleBot 4 Lite 成功离座、SLAM 建图、到达首个自主探索目标，并选出第二目标。 / TurtleBot 4 Lite undocked, SLAM built a map, the first autonomous frontier was reached, and a second goal was selected. | 测试在探索完成前结束；未完成识人、接近及返程的端到端测试。 / The trial ended before exploration completed; detection, approach and return were not tested end to end. |

三维场景使用静止的人形占位模型，并非已接入的人员识别。运行日志保存在 Ge Mei 的本机测试工作区，未包含在本交付目录中。三维 Gazebo 测试使用 `LIBGL_ALWAYS_SOFTWARE=1` 处理虚拟机画面问题；它不是导航算法的一部分。

The 3D scene used stationary person-shaped placeholders, not integrated person recognition. Run logs remain in Ge Mei's local test workspace and are not part of this handoff. The 3D Gazebo trial used `LIBGL_ALWAYS_SOFTWARE=1` for VM rendering; it is not part of the navigation algorithm.

在仓库根目录可独立重跑栅格单元测试： / Run the grid unit tests independently from the repository root:

```bash
PYTHONPATH=scr/meg_navigation python3 -m unittest discover -s scr/meg_navigation/test -v
```

## 7. 尚需联调与已知限制 / Pending integration and limitations

- **视觉坐标接入 / Vision coordinates:** 双目检测结果需要经过相机标定、目标筛选和 TF 转换后发布为 `map` 坐标系中的 `/rescue_target`；本包尚未验证该链路。 / Stereo detections must be calibrated, filtered, transformed by TF, and published as `/rescue_target` in `map`; this path is unverified.
- **记录确认 / Recording acknowledgement:** 默认任务等待 `/rescue_recorded=true`；需要队友的记录模块在实际保存完成后发布，随后测试返程。 / The default mission waits for `/rescue_recorded=true`; the recording module must publish it after saving, followed by a return test.
- **完整三维任务 / Complete 3D mission:** 尚未证明从未知场景探索到识人、接近、记录和返程能够一次跑通。 / A single 3D run from unknown-map exploration through detection, approach, recording and return has not been demonstrated.
- **适用范围 / Operating scope:** 当前以二维占据地图规划平面路线，每次任务处理一个目标；动态人员追踪、楼梯和非平坦地形不在已验证范围内。 / The current planner uses a 2D occupancy grid and handles one target per run; moving-person tracking, stairs and uneven terrain are outside the verified scope.

Nav2 参数基于 TurtleBot 4 Jazzy 配置修改；许可证见 [`meg_navigation/LICENSE`](LICENSE)。

The Nav2 parameters are adapted from the TurtleBot 4 Jazzy configuration; see [`meg_navigation/LICENSE`](LICENSE).
