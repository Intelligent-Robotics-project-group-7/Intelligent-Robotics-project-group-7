"""Start Meg's Nav2 A* stack and mission using an externally supplied map/TF."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import os


def generate_launch_description():
    tb4_share = get_package_share_directory('turtlebot4_navigation')
    own_share = get_package_share_directory('meg_navigation')
    use_sim_time = LaunchConfiguration('use_sim_time')
    start_mission = LaunchConfiguration('start_mission')
    require_recording_ack = LaunchConfiguration('require_recording_ack')

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb4_share, 'launch', 'nav2.launch.py')),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'params_file': os.path.join(own_share, 'config', 'nav2_tb4_astar.yaml'),
        }.items(),
    )
    mission = Node(
        package='meg_navigation',
        executable='rescue_mission',
        name='meg_rescue_mission',
        output='screen',
        parameters=[{
            'use_sim_time': ParameterValue(use_sim_time, value_type=bool),
            'require_recording_ack': ParameterValue(require_recording_ack,
                                                    value_type=bool),
        }],
        condition=IfCondition(start_mission),
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('start_mission', default_value='true'),
        DeclareLaunchArgument('require_recording_ack', default_value='true'),
        nav2,
        mission,
    ])
