# Group 7 TurtleBot 4 project

The `src/` directory contains the code collected from the team branches. Each folder keeps its own setup and launch instructions.

| Directory | Contents | Source branch and revision |
| --- | --- | --- |
| [`src/localisation_mapping/`](src/localisation_mapping/) | ROS 2 mapping package | [`feature/localisation-mapping` at `26b60f4`](https://github.com/Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7/commit/26b60f4944070b1ba1a70c236ae9ed4abb06ae3a) |
| [`src/meg_navigation/`](src/meg_navigation/) | ROS 2 navigation package | [`navigation/GeMei` at `bc35521`](https://github.com/Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7/commit/bc35521351b4dc035a31b94097bc36d2ae35c8f0) |
| [`src/turtlebot4_scene/`](src/turtlebot4_scene/) | Shared Gazebo world and actor mesh | [`sim/turtlebot4-scene-only` at `5f46281`](https://github.com/Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7/commit/5f46281ff106166d73ecc42a99e4cd01b5a716b1) |
| [`src/robot-CV/`](src/robot-CV/) | Detection, depth estimation, and target tracking through Phase 4 | [`robot-CV` at `00889bd`](https://github.com/Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7/commit/00889bd30e67313333e7fc9b1cc8255336511897) |
| [`src/robotcv2/`](src/robotcv2/) | Selectable YOLO models and centre-pixel ranging | [`robotcv2` at `aaff8a0`](https://github.com/Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7/commit/aaff8a0d078094c6f85deed78a4617647f4c262e) |
| [`src/robotcv3/`](src/robotcv3/) | Pose keypoints and depth outlier rejection | [`robotcv3` at `135b5d9`](https://github.com/Intelligent-Robotics-project-group-7/Intelligent-Robotics-project-group-7/commit/135b5d9faae916771161e87c3b0e246024a9795d) |

The mapping and simulation branches contain the same scene files. The shared copy is in `src/turtlebot4_scene/`. The CV folders are standalone variants with overlapping ROS topics. Use the instructions in the variant you want to run. End-to-end navigation, mapping, and perception integration remains to be validated.
