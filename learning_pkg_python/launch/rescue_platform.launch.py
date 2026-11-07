import sys

from pathlib import Path

from launch import LaunchDescription
from launch.actions import ExecuteProcess, DeclareLaunchArgument, SetEnvironmentVariable
from launch_ros.actions import Node
def generate_launch_description():
    
    # make sure document path is correct 
    package_dir = Path(__file__).resolve().parents[1]
    # world map
    world = str(package_dir / "worlds" / "navigation_test.sdf") 
    # car model
    resource_path = str(package_dir / "models")         
    # gz-ros bridge   
    bridge_path = str(package_dir / "config" / "bridge_rescue.yaml")

    rviz_config = str(package_dir/ "config" / "robot_view.rviz")

    task = [

        SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH",resource_path),

        ExecuteProcess(
        cmd =["gz","sim","-r", world],
        additional_env={"LIBGL_ALWAYS_SOFTWARE":"1"},# use only CPU
        output = "screen"),

    ]

    gz_bridge = Node(
        package = "ros_gz_bridge",
        executable= "parameter_bridge",
        name = "bridge_rescue",
        parameters = [
            {"config_file": bridge_path}
        ],
        output="screen",
    )
    task.append(gz_bridge)

    rviz_cfg = Node(
        package = "rviz2",
        executable= "rviz2",
        name = "rviz2",
        arguments = [
            "-d", rviz_config
        ],
        parameters=[{"use_sim_time":True}],
        additional_env={"LIBGL_ALWAYS_SOFTWARE":"1"},# use only CPU
        output="screen",
    )
    task.append(rviz_cfg)

    # ZH: 读取原始轮式里程计，发布带噪 /odom 和 odom → base_link。
    # EN: Read raw wheel odometry and publish noisy /odom and odom → base_link.
    task.append(
        ExecuteProcess(
            cmd=[
                sys.executable,
                str(package_dir / "learning_pkg_python" / "noisy_odom_node.py"),
                "--ros-args",
                "--params-file",
                str(package_dir / "config" / "odom_noise_rescue.yaml"),
            ],
            output="screen",
        )
    )

    lidar_tf = Node(
        package = "tf2_ros",
        executable= "static_transform_publisher",
        name = "static_lidar_tf",
        arguments = [
            '--x','0.03','--y','0', '--z','0.48',
            '--roll','0','--pitch','0','--yaw','0',
            '--frame-id','base_link',
            '--child-frame-id','laser_frame',
        ],
        parameters=[{"use_sim_time":True}],
        output="screen",
    )
    task.append(lidar_tf)

    imu_tf = Node(
        package = "tf2_ros",
        executable= "static_transform_publisher",
        name = "static_imu_tf",
        arguments = [
            '--x','0','--y','0', '--z','0.1',
            '--roll','0','--pitch','0','--yaw','0',
            '--frame-id','base_link',
            '--child-frame-id','imu_link',
        ],
        parameters=[{"use_sim_time":True}],
        output="screen",
    )
    task.append(imu_tf)

    stereo_camera_link_tf = Node(
        package = "tf2_ros",
        executable= "static_transform_publisher",
        name = "stereo_camera_link_tf",
        arguments = [
            '--x','0.421','--y','0', '--z','0.32',
            '--roll','0','--pitch','0','--yaw','0',
            '--frame-id','base_link',
            '--child-frame-id','stereo_camera_link',
        ],
        parameters=[{"use_sim_time":True}],
        output="screen",
    )
    task.append(stereo_camera_link_tf)

    left_camera_tf = Node(
        package = "tf2_ros",
        executable= "static_transform_publisher",
        name = "left_camera_tf",
        arguments = [
            '--x','0','--y','0.06', '--z','0',
            '--roll','0','--pitch','0','--yaw','0',
            '--frame-id','stereo_camera_link',
            '--child-frame-id','left_camera_link',
        ],
        parameters=[{"use_sim_time":True}],
        output="screen",
    )
    task.append(left_camera_tf)

    stereo_left_tf = Node(
        package = "tf2_ros",
        executable= "static_transform_publisher",
        name = "stereo_left_tf",
        arguments = [
            '--x','0','--y','0', '--z','0',
            '--roll','-1.5707963267948966','--pitch','0','--yaw','-1.5707963267948966',
            '--frame-id','left_camera_link',
            '--child-frame-id','left_camera_optical_frame',
        ],
        parameters=[{"use_sim_time":True}],
        output="screen",
    )
    task.append(stereo_left_tf)

    right_camera_tf = Node(
        package = "tf2_ros",
        executable= "static_transform_publisher",
        name = "right_camera_tf",
        arguments = [
            '--x','0','--y','-0.06', '--z','0',
            '--roll','0','--pitch','0','--yaw','0',
            '--frame-id','stereo_camera_link',
            '--child-frame-id','right_camera_link',
        ],
        parameters=[{"use_sim_time":True}],
        output="screen",
    )
    task.append(right_camera_tf)

    stereo_right_tf = Node(
        package = "tf2_ros",
        executable= "static_transform_publisher",
        name = "stereo_right_tf",
        arguments = [
            '--x','0','--y','0', '--z','0',
            '--roll','-1.5707963267948966','--pitch','0','--yaw','-1.5707963267948966',
            '--frame-id','right_camera_link',
            '--child-frame-id','right_camera_optical_frame',
        ],
        parameters=[{"use_sim_time":True}],
        output="screen",
    )
    task.append(stereo_right_tf)

    return LaunchDescription(task)