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
    track = LaunchConfiguration('tracking').perform(context) == 'true'
    use_depth = LaunchConfiguration('tracking_depth').perform(context)
    if track and phase != '3':
        raise ValueError('Tracking uses the Phase 3 RGB-D scene')
    model_path = get_model_path(LaunchConfiguration('model').perform(context))
    generated = root / f'downloads/phase{phase}/generated' / case_id
    description = (generated / 'robot.urdf').read_text()
    camera = '/world/person_eval/model/turtlebot4/link/oakd_rgb_camera_frame/sensor/rgbd_camera/'
    lidar = '/world/person_eval/model/turtlebot4/link/rplidar_link/sensor/rplidar/scan'
    detector_params = {'detection.model_path': str(model_path)}
    adapter_args = []
    if track:
        from person_tracking import LOW_SCORE
        detector_params['detection.threshold'] = LOW_SCORE
        adapter_args = ['--ros-args', '-p', f'minimum_score:={LOW_SCORE}']
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
             parameters=[str(root / 'config/person_detection.yaml'), detector_params]),
        ExecuteProcess(cmd=['python3', str(root / 'scripts/person_detection_adapter.py'), *adapter_args], output='screen'),
        ExecuteProcess(cmd=['python3', str(root / 'scripts/drive_virtual_people.py'), case_id, '--phase', phase], output='screen'),
    ]
    if phase == '3':
        actions.append(ExecuteProcess(cmd=['python3', str(root / 'scripts/person_depth_node.py')], output='screen'))
    if track:
        actions.append(ExecuteProcess(cmd=['python3', str(root / 'scripts/person_tracking_node.py'),
                                           '--ros-args', '-p', f'use_depth:={use_depth}'], output='screen'))
    return actions


def generate_launch_description():
    catalog = model_catalog()
    return LaunchDescription([DeclareLaunchArgument('case', default_value='single_front'),
                              DeclareLaunchArgument('phase', default_value='2', choices=['2', '3']),
                              DeclareLaunchArgument('model', default_value=catalog['default_model'],
                                                    choices=list(catalog['models'])),
                              DeclareLaunchArgument('tracking', default_value='false', choices=['false', 'true']),
                              DeclareLaunchArgument('tracking_depth', default_value='true', choices=['false', 'true']),
                              OpaqueFunction(function=setup)])
