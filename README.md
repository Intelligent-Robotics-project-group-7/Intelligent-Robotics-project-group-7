# TurtleBot 4 搜救导航

## 1. 项目介绍

`meg_navigation` 是搜救项目的导航模块，负责让 TurtleBot 4 在未知的室内环境中探索，收到人员位置后开到附近，再返回任务起点。即使在三维 Gazebo 场景中，机器人也是根据二维地面地图规划路线。

## 2. 已实现功能

- **自主探索** — 从地图上找出靠近未知区域且可以到达的探索点，无需手动输入一串导航目标。
- **A* 路径规划** — 用栅格 A* 检查候选目标能否到达，交由 Nav2 的 `SmacPlanner2D` 计算全局行驶路线。
- **接近人员与返程** — 收到地图上的人员位置后，选择距该位置约 0.8 米的可达停车点。默认在收到记录确认后返程，每次运行处理一个目标。
- **离座与任务状态** — 小车在充电座上时先离座，并在运行中报告探索、接近、等待记录和返程等状态。

**测试结果**

| 场景 | 结果 |
| --- | --- |
| 栅格单元测试 | 7 项通过。 |
| 二维门洞与绕墙场景 | 使用测试程序提供的目标，关闭记录确认后，完成探索、接近和返程。 |
| 二维双隔墙场景 | 一次运行中接近成功，返程失败。 |
| Gazebo 三维房间 | TurtleBot 4 Lite 离座并到达第一个自主探索点，随后发送第二个目标。人员识别、记录与返程尚未在同一次三维任务中跑通。 |

## 3. 系统架构

建图模块提供地图和定位数据。任务节点决定小车下一站去哪，Nav2 规划路线、跟踪路径，并通过雷达数据处理障碍物。人员检测与记录由对应的外部模块完成。

1. **准备**  
   等待地图和 Nav2 就绪。小车在充电座上时，先离座，再记录当前地图坐标作为返程点。
2. **探索**  
   从已知可通行区域的边缘选择探索点，用 A* 检查可达性，再交给 Nav2。地图更新后继续选择下一站。
3. **接近**  
   收到第一个有效的人员位置后，寻找可以到达的停车点。附近地图还不完整时，继续探索。
4. **记录与返程**  
   到达停车点后，默认等待记录程序确认保存完成，再让 Nav2 返回起点。返程成功时发布 `DONE`，任务失败时发布 `FAILED` 和原因。

## 4. 运行环境与依赖

| 用途 | 环境或依赖 |
| --- | --- |
| 系统与 Python | Ubuntu 24.04、Python 3.12。 |
| ROS 与构建工具 | ROS 2 Jazzy、`colcon`、`rosdep`。 |
| 导航 | `turtlebot4_navigation`、Nav2（含 `nav2_smac_planner`）、`irobot_create_msgs`。Python 节点使用 `rclpy` 和 `tf2_ros`。 |
| 仿真与建图 | Gazebo Harmonic、TurtleBot 4 仿真包、SLAM Toolbox。 |

ROS 包的完整依赖列表见 [package.xml](meg_navigation/package.xml)。测试命令使用 Python 自带的 `unittest`。

## 5. 文件结构

| 路径 | 用途 |
| --- | --- |
| [meg_navigation/grid.py](meg_navigation/meg_navigation/grid.py) | 栅格地图、A* 搜索、探索点与停车点选择。 |
| [meg_navigation/mission.py](meg_navigation/meg_navigation/mission.py) | 管理任务流程，接收人员位置和记录确认，向 Nav2 发送目标。 |
| [config/nav2_tb4_astar.yaml](meg_navigation/config/nav2_tb4_astar.yaml) | 配置全局规划器、路径跟踪控制器、代价地图和碰撞监测。 |
| [launch/navigation.launch.py](meg_navigation/launch/navigation.launch.py) | 启动 Nav2 和搜救任务节点。 |
| [test/test_grid.py](meg_navigation/test/test_grid.py) | 测试 A*、未知区域与障碍物处理、目标点选择。 |
| [package.xml](meg_navigation/package.xml)、[setup.py](meg_navigation/setup.py)、[setup.cfg](meg_navigation/setup.cfg)、[resource/meg_navigation](meg_navigation/resource/meg_navigation) | 声明依赖、安装 Python 入口，并将包注册到 ROS 2。 |

## 6. 安装与运行

从团队仓库的 `navigation/GeMei` 分支取得 `meg_navigation/`，进入包含该文件夹的目录。安装 ROS 2 Jazzy 并配置 ROS 软件源后，安装构建工具和仿真包。

```bash
sudo apt update
sudo apt install python3-colcon-common-extensions python3-rosdep ros-jazzy-turtlebot4-simulator
```

首次使用 `rosdep` 时执行一次 `sudo rosdep init`，再执行 `rosdep update`。随后安装 ROS 依赖并构建本包。

```bash
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths meg_navigation --ignore-src --rosdistro jazzy -y
colcon build --symlink-install --base-paths meg_navigation --packages-select meg_navigation
source install/setup.bash
```

仿真、建图和导航分别在三个终端中运行。每个终端先加载 ROS 环境，导航终端还需要加载刚构建的 `install/setup.bash`。下面用 TurtleBot 4 自带的 `depot` 场景演示启动顺序，三维测试记录来自单独的房间场景。团队如已启动自己的仿真与建图，只需执行第三步。

```bash
# 1. 仿真与 RViz
ros2 launch turtlebot4_gz_bringup turtlebot4_gz.launch.py world:=depot rviz:=true

# 2. 建图与定位
ros2 launch turtlebot4_navigation slam.launch.py use_sim_time:=true

# 3. 地图可用后启动导航
ros2 launch meg_navigation navigation.launch.py
```

默认启动 Nav2 和任务节点，使用仿真时间并等待记录确认。只启动 Nav2 时加 `start_mission:=false`。使用测试目标单独验证导航时，可加 `require_recording_ack:=false` 跳过记录确认。

在其他终端分别查看任务状态和规划路径。状态在变化时发布，建议在启动任务前订阅。看到 `EXPLORING:` 表示小车已开始自主探索。查看路径时，订阅后等待下一次规划。也可以在 RViz 添加 **Path**，选择 `/plan` 并将 **Fixed Frame** 设为 `map`。

```bash
ros2 topic echo /meg_navigation/status std_msgs/msg/String
ros2 topic echo /plan nav_msgs/msg/Path --once
```

在包含 `meg_navigation/` 的目录中运行算法单元测试。

```bash
PYTHONPATH=meg_navigation python3 -m unittest discover -s meg_navigation/test -v
```

## 7. ROS 2 接口

以下名称适用于默认的单机器人配置。

| 话题 | 消息类型 | 数据流与用途 |
| --- | --- | --- |
| `/plan` | `nav_msgs/msg/Path` | Nav2 发布的全局规划路径，使用 `map` 坐标系。 |
| `/map` | `nav_msgs/msg/OccupancyGrid` | 建图模块向任务节点和 Nav2 提供二维地图。 |
| `/scan` | `sensor_msgs/msg/LaserScan` | 雷达数据供建图和 Nav2 使用。 |
| `/odom` | `nav_msgs/msg/Odometry` | 底盘向 Nav2 提供里程计数据。 |
| `/tf`、`/tf_static` | `tf2_msgs/msg/TFMessage` | 提供 `map → odom → base_link` 及传感器安装位置的坐标变换。 |
| `/clock` | `rosgraph_msgs/msg/Clock` | Gazebo 提供仿真时钟。 |
| `/dock_status` | `irobot_create_msgs/msg/DockStatus` | 底盘向任务节点报告 `is_docked`。 |
| `/cmd_vel_nav` | `geometry_msgs/msg/TwistStamped` | Nav2 向速度平滑器发送原始速度指令。 |
| `/cmd_vel_smoothed` | `geometry_msgs/msg/TwistStamped` | 速度平滑器向碰撞监测节点发送平滑后的指令。 |
| `/cmd_vel` | `geometry_msgs/msg/TwistStamped` | 碰撞监测节点向底盘发送正常导航时的最终速度指令。 |
| `/global_costmap/costmap`、`/local_costmap/costmap` | `nav_msgs/msg/OccupancyGrid` | Nav2 发布的全局和局部代价地图，可在 RViz 中查看。 |
| `/collision_monitor_state` | `nav2_msgs/msg/CollisionMonitorState` | 碰撞监测的动作状态。 |
| `/rescue_target` | `geometry_msgs/msg/PointStamped` | 感知模块向任务节点提供人员位置。`header.frame_id` 为 `map`，`point.x/y` 为有限数值，单位为米。 |
| `/rescue_recorded` | `std_msgs/msg/Bool` | 记录模块收到 `WAIT_RECORDING:` 后保存信息，再发布 `data=true`。 |
| `/meg_navigation/status` | `std_msgs/msg/String` | 任务节点发布状态和说明，例如 `WAIT_RECORDING:`、`RETURNING:`、`DONE:` 或 `FAILED:`。 |

接入相机时，先根据相机安装位置和拍摄时小车在地图中的位置与朝向，把检测点换算为地图坐标，再发布 `/rescue_target`。这一环节仍待联调。接入团队的避障程序时，先约定它接收哪一路速度指令，以及由哪个节点向底盘发布最终的 `/cmd_vel`。

| 动作或服务 | 类型 | 用途 |
| --- | --- | --- |
| `/navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | 任务节点发送探索、接近和返程的目标位姿，Nav2 返回执行结果。 |
| `/compute_path_to_pose` | `nav2_msgs/action/ComputePathToPose` | 计算到目标的路径，在结果的 `path` 字段返回。 |
| `/follow_path` | `nav2_msgs/action/FollowPath` | Nav2 控制器执行给定路径。 |
| `/undock` | `irobot_create_msgs/action/Undock` | 任务节点请求 TurtleBot 4 离座。 |
| `/bt_navigator/get_state` | `lifecycle_msgs/srv/GetState` | 任务节点检查 Nav2 是否已激活。 |

地图发布端使用 Reliable 和 Transient Local QoS。人员位置、记录确认和任务状态使用 Reliable、Volatile、队列深度 10。运行时可用 `ros2 topic list -t` 和 `ros2 action list -t` 核对名称及类型。

---

# TurtleBot 4 Search and Rescue Navigation

## 1. Project Overview

`meg_navigation` is the navigation module for the search and rescue project. It lets a TurtleBot 4 explore an unmapped indoor area, approach a reported person location, and return to its starting point. In a 3D Gazebo scene, the robot still plans on a 2D map of the floor.

## 2. Features

- **Autonomous exploration** — Select reachable goals near unexplored areas without a manually supplied list of waypoints.
- **A* path planning** — Check candidate goals with grid A*, then use Nav2's `SmacPlanner2D` to plan the global route.
- **Person approach and return** — Select a reachable stopping point about 0.8 m from the reported person. By default, return after recording is confirmed. Each run handles one target.
- **Undocking and mission status** — Undock when needed and report progress through exploration, approach, recording and return.

**Test results**

| Scenario | Result |
| --- | --- |
| Grid unit tests | All 7 tests passed. |
| 2D doorway and detour scenes | Exploration, approach and return completed with simulated targets and recording acknowledgement disabled. |
| 2D two-partition scene | One run reached the approach point but failed to return. |
| 3D Gazebo room | The TurtleBot 4 Lite undocked, reached its first autonomous exploration goal, and sent a second goal. Person detection, recording and return have yet to be verified in one 3D run. |

## 3. System Architecture

The mapping stack provides the map and localisation. The mission node chooses the next destination. Nav2 plans and follows the route and uses lidar data to respond to obstacles. Separate modules provide person detections and save the rescue record.

1. **Initialise**  
   Wait for the map and Nav2. Undock if needed, then save the current map coordinates as the return point.
2. **Explore**  
   Choose a goal near the edge of known free space, check it with A*, and send it to Nav2. Use map updates to choose the next goal.
3. **Approach**  
   After receiving the first valid person location, find a reachable stopping point nearby. Keep exploring if the area has not been mapped well enough to plan an approach.
4. **Record and return**  
   After reaching the stopping point, wait for the recording program to confirm that it has saved the information, then ask Nav2 to return to the start. The mission reports `DONE` after a successful return or `FAILED` with the reason.

## 4. Requirements

| Purpose | Environment or dependency |
| --- | --- |
| OS and Python | Ubuntu 24.04 and Python 3.12. |
| ROS and build tools | ROS 2 Jazzy, `colcon` and `rosdep`. |
| Navigation | `turtlebot4_navigation`, Nav2 including `nav2_smac_planner`, and `irobot_create_msgs`. The Python node uses `rclpy` and `tf2_ros`. |
| Simulation and mapping | Gazebo Harmonic, TurtleBot 4 simulator packages, and SLAM Toolbox. |

See [package.xml](meg_navigation/package.xml) for the full list of ROS package dependencies. The test command uses Python's built-in `unittest`.

## 5. Package Structure

| Path | Purpose |
| --- | --- |
| [meg_navigation/grid.py](meg_navigation/meg_navigation/grid.py) | Occupancy grid, A* search, and selection of exploration and stopping points. |
| [meg_navigation/mission.py](meg_navigation/meg_navigation/mission.py) | Runs the mission, receives person locations and recording acknowledgements, and sends goals to Nav2. |
| [config/nav2_tb4_astar.yaml](meg_navigation/config/nav2_tb4_astar.yaml) | Configures the global planner, path tracking controller, costmaps and collision monitor. |
| [launch/navigation.launch.py](meg_navigation/launch/navigation.launch.py) | Starts Nav2 and the rescue mission node. |
| [test/test_grid.py](meg_navigation/test/test_grid.py) | Tests A*, handling of unknown space and obstacles, and goal selection. |
| [package.xml](meg_navigation/package.xml), [setup.py](meg_navigation/setup.py), [setup.cfg](meg_navigation/setup.cfg), [resource/meg_navigation](meg_navigation/resource/meg_navigation) | Declare dependencies, install the Python entry point, and register the package with ROS 2. |

## 6. Installation & Usage

Get `meg_navigation/` from the team's `navigation/GeMei` branch and open the directory that contains it. Install ROS 2 Jazzy and configure the ROS package repository before installing the build tools and simulator.

```bash
sudo apt update
sudo apt install python3-colcon-common-extensions python3-rosdep ros-jazzy-turtlebot4-simulator
```

For first-time `rosdep` setup, run `sudo rosdep init` once, followed by `rosdep update`. Then install the ROS dependencies and build the package.

```bash
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths meg_navigation --ignore-src --rosdistro jazzy -y
colcon build --symlink-install --base-paths meg_navigation --packages-select meg_navigation
source install/setup.bash
```

Run simulation, mapping and navigation in separate terminals. Source the ROS environment in each terminal and the built `install/setup.bash` in the navigation terminal. This startup example uses the bundled TurtleBot 4 `depot` world. The recorded 3D trial used a separate room scene. If the team already runs its own simulation and mapping, start at step 3.

```bash
# 1. Simulation and RViz
ros2 launch turtlebot4_gz_bringup turtlebot4_gz.launch.py world:=depot rviz:=true

# 2. Mapping and localisation
ros2 launch turtlebot4_navigation slam.launch.py use_sim_time:=true

# 3. Start navigation once the map is available
ros2 launch meg_navigation navigation.launch.py
```

The default launch starts Nav2 and the mission, uses simulation time, and requires recording acknowledgement. Add `start_mission:=false` to start only Nav2. For an isolated navigation test with a test target, add `require_recording_ack:=false` to bypass the recording acknowledgement.

Use separate terminals to monitor mission status and planned paths. Status is published when it changes, so subscribe before starting the mission. `EXPLORING:` indicates that autonomous exploration has started. Subscribe to paths before the next plan is generated. In RViz, add a **Path** display for `/plan` and set **Fixed Frame** to `map`.

```bash
ros2 topic echo /meg_navigation/status std_msgs/msg/String
ros2 topic echo /plan nav_msgs/msg/Path --once
```

Run the grid unit tests from the directory containing `meg_navigation/`.

```bash
PYTHONPATH=meg_navigation python3 -m unittest discover -s meg_navigation/test -v
```

## 7. ROS 2 Interfaces

Names below apply to the default single-robot setup.

| Topic | Message type | Data flow and purpose |
| --- | --- | --- |
| `/plan` | `nav_msgs/msg/Path` | Global route published by Nav2 in the `map` frame. |
| `/map` | `nav_msgs/msg/OccupancyGrid` | Mapping supplies the 2D map to the mission and Nav2. |
| `/scan` | `sensor_msgs/msg/LaserScan` | Lidar data for mapping and Nav2. |
| `/odom` | `nav_msgs/msg/Odometry` | The base supplies odometry to Nav2. |
| `/tf`, `/tf_static` | `tf2_msgs/msg/TFMessage` | Carry transforms for `map → odom → base_link` and the sensor mounts. |
| `/clock` | `rosgraph_msgs/msg/Clock` | Simulation clock from Gazebo. |
| `/dock_status` | `irobot_create_msgs/msg/DockStatus` | The base reports `is_docked` to the mission node. |
| `/cmd_vel_nav` | `geometry_msgs/msg/TwistStamped` | Nav2 sends the requested velocity to the velocity smoother. |
| `/cmd_vel_smoothed` | `geometry_msgs/msg/TwistStamped` | The velocity smoother sends the smoothed command to the collision monitor. |
| `/cmd_vel` | `geometry_msgs/msg/TwistStamped` | The collision monitor sends the final velocity command to the base during navigation. |
| `/global_costmap/costmap`, `/local_costmap/costmap` | `nav_msgs/msg/OccupancyGrid` | Global and local costmaps published by Nav2 for inspection in RViz. |
| `/collision_monitor_state` | `nav2_msgs/msg/CollisionMonitorState` | Collision monitor action state. |
| `/rescue_target` | `geometry_msgs/msg/PointStamped` | Perception provides a person location to the mission node. Set `header.frame_id` to `map` and use finite `point.x/y` values in metres. |
| `/rescue_recorded` | `std_msgs/msg/Bool` | The recording module saves the information after `WAIT_RECORDING:` and then publishes `data=true`. |
| `/meg_navigation/status` | `std_msgs/msg/String` | The mission publishes a state and detail, such as `WAIT_RECORDING:`, `RETURNING:`, `DONE:` or `FAILED:`. |

For camera integration, use the camera mounting transform and the robot's pose at the time of detection to convert the point to map coordinates before publishing `/rescue_target`. This conversion is pending integration. When connecting the team's obstacle avoidance module, agree on which velocity topic it reads and which node sends the final `/cmd_vel` to the base.

| Action or service | Type | Purpose |
| --- | --- | --- |
| `/navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | The mission sends exploration, approach and return poses, and Nav2 returns the outcome. |
| `/compute_path_to_pose` | `nav2_msgs/action/ComputePathToPose` | Computes a route and returns it in the result's `path` field. |
| `/follow_path` | `nav2_msgs/action/FollowPath` | The Nav2 controller follows a given path. |
| `/undock` | `irobot_create_msgs/action/Undock` | The mission asks TurtleBot 4 to leave the dock. |
| `/bt_navigator/get_state` | `lifecycle_msgs/srv/GetState` | The mission checks whether Nav2 is active. |

The map publisher uses Reliable and Transient Local QoS. Person location, recording acknowledgement and mission status use Reliable and Volatile QoS with a queue depth of 10. Use `ros2 topic list -t` and `ros2 action list -t` to check names and types at runtime.
