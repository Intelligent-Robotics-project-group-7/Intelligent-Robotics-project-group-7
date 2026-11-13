"""Stationary simulation with independent truth and optional depth estimates."""
import os
import sys
from pathlib import Path
from ament_index_python.packages import get_package_share_directory as share
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, OpaqueFunction, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from person_models import get_model_path, model_catalog


def setup(context):
    root = ROOT
    case_id = LaunchConfiguration('case').perform(context)
    phase = LaunchConfiguration('phase').perform(context)
    model_path = get_model_path(LaunchConfiguration('model').perform(context))
    generated = root / f'downloads/phase{phase}/generated' / case_id
    description = (generated / 'robot.urdf').read_text()
    camera = '/world/person_eval/model/turtlebot4/link/oakd_rgb_camera_frame/sensor/rgbd_camera/'
    lidar = '/world/person_eval/model/turtlebot4/link/rplidar_link/sensor/rplidar/scan'
    actions = [
        SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', ':'.join([
            str(Path(share('turtlebot4_description')).parent),
            str(Path(share('irobot_create_description')).parent), str(root / 'downloads/phase2')])),
        SetEnvironmentVariable('GZ_PARTITION', f'tb4_research_phase{phase}_' + case_id),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(os.path.join(share('ros_gz_sim'), 'launch/gz_sim.launch.py')),
                                 launch_arguments={'gz_args': '-r -s --render-engine-server ogre2 ' + str(generated / 'world.sdf')}.items()),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             parameters=[{'robot_description': description, 'use_sim_time': True}]),
        Node(package='joint_state_publisher', executable='joint_state_publisher', parameters=[{'use_sim_time': True}]),
        Node(package='ros_gz_sim', executable='create',
             arguments=['-world', 'person_eval', '-name', 'turtlebot4', '-z', '0.01', '-topic', 'robot_description']),
        Node(package='ros_gz_bridge', executable='parameter_bridge', name='sensor_bridge',
             arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
                        camera + 'image@sensor_msgs/msg/Image[gz.msgs.Image',
                        camera + 'depth_image@sensor_msgs/msg/Image[gz.msgs.Image',
                        camera + 'camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo',
                        lidar + '@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan',
                        '/evaluation/semantic/labels_map@sensor_msgs/msg/Image[gz.msgs.Image'],
             remappings=[(camera + 'image', '/oakd/rgb/preview/image_raw'),
                         (camera + 'depth_image', '/oakd/rgb/preview/depth'),
                         (camera + 'camera_info', '/oakd/rgb/preview/camera_info'), (lidar, '/scan')]),
        Node(package='yolo_ros', executable='yolo_node', name='yolo_node', namespace='yolo',
             parameters=[str(root / 'config/person_detection.yaml'), {'detection.model_path': str(model_path)}]),
        ExecuteProcess(cmd=['python3', str(root / 'scripts/person_detection_adapter.py')], output='screen'),
        ExecuteProcess(cmd=['python3', str(root / 'scripts/drive_virtual_people.py'), case_id, '--phase', phase], output='screen'),
    ]
    if phase == '3':
        actions.append(ExecuteProcess(cmd=['python3', str(root / 'scripts/person_depth_node.py')], output='screen'))
    return actions


def generate_launch_description():
    catalog = model_catalog()
    return LaunchDescription([DeclareLaunchArgument('case', default_value='single_front'),
                              DeclareLaunchArgument('phase', default_value='2', choices=['2', '3']),
                              DeclareLaunchArgument('model', default_value=catalog['default_model'],
                                                    choices=list(catalog['models'])),
                              OpaqueFunction(function=setup)])
