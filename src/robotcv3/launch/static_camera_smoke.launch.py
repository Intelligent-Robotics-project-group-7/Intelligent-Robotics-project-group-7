"""Offline, stationary official TurtleBot 4 model; navigation remains disabled."""
import os
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory
    project = Path(__file__).resolve().parents[1]
    resources = ':'.join([
        str(Path(share('turtlebot4_description')).parent),
        str(Path(share('irobot_create_description')).parent),
    ])
    camera_prefix = '/world/camera_smoke/model/turtlebot4/link/oakd_rgb_camera_frame/sensor/rgbd_camera/'
    lidar_topic = '/world/camera_smoke/model/turtlebot4/link/rplidar_link/sensor/rplidar/scan'
    return LaunchDescription([
        SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', resources),
        SetEnvironmentVariable('GZ_PARTITION', 'tb4_research_step1'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(share('ros_gz_sim'), 'launch/gz_sim.launch.py')),
            launch_arguments={'gz_args': '-r -s --render-engine-server ogre2 ' + str(project / 'worlds/camera_smoke.sdf')}.items()),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(share('turtlebot4_description'), 'launch/robot_description.launch.py')),
            launch_arguments={'model': 'standard', 'namespace': '', 'use_sim_time': 'true'}.items()),
        Node(package='ros_gz_sim', executable='create',
             arguments=['-world', 'camera_smoke', '-name', 'turtlebot4', '-z', '0.01', '-topic', 'robot_description']),
        # Sensor-only, GZ->ROS bridges. No velocity bridge, platform mocks or navigation.
        Node(package='ros_gz_bridge', executable='parameter_bridge', name='sensor_bridge',
             arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
                        camera_prefix + 'image@sensor_msgs/msg/Image[gz.msgs.Image',
                        camera_prefix + 'depth_image@sensor_msgs/msg/Image[gz.msgs.Image',
                        camera_prefix + 'camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo',
                        lidar_topic + '@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan'],
             remappings=[(camera_prefix + 'image', '/oakd/rgb/preview/image_raw'),
                         (camera_prefix + 'depth_image', '/oakd/rgb/preview/depth'),
                         (camera_prefix + 'camera_info', '/oakd/rgb/preview/camera_info'),
                         (lidar_topic, '/scan')]),
        Node(package='tf2_ros', executable='static_transform_publisher',
             arguments=['--x', '0', '--y', '0', '--z', '0', '--roll', '0',
                        '--pitch', '-1.5707', '--yaw', '1.5707',
                        '--frame-id', 'oakd_rgb_camera_optical_frame',
                        '--child-frame-id', 'turtlebot4/oakd_rgb_camera_frame/rgbd_camera']),
        Node(package='tf2_ros', executable='static_transform_publisher',
             arguments=['--frame-id', 'rplidar_link', '--child-frame-id', 'turtlebot4/rplidar_link/rplidar']),
    ])
