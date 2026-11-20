import math
import random

import rclpy
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import Buffer, TransformException, TransformListener

import numpy as np
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from tf2_ros import TransformBroadcaster
from std_msgs.msg import Int32

# Topic Name
# SLAM_Topic = 
# A_Star_Topic = 
Odometry_Topic = '/odom'
LiDAR_Topic = '/scan'
# Localisation_Topic = 
# vehicle_size =

# dwa entrance
# dwa evaluation
# dwa calculating
# dwa distance_obstacle
# dwa trajectory_predict
# dwa subsribe
# dwa publish



class DWA_run(Node):
    def __init__(self):
        super().__init__('dwa_node')

        self.tf_buffer = Buffer(node=self)
        self.tf_listener = TransformListener(self.tf_buffer, self)

        
        self.latest_scan = None
        self.latest_odom = None
        self.latest_pose = None
        self.v_max = 0.31
        self.w_max = 1.90
        self.w_min = -1.90
        self.v_a_max = 2.5
        self.v_a_min = -2.5
        self.w_a_max = 2.5
        self.w_a_min = -3.2

        # ZH: 每 0.1 秒执行一次 control_step，目标频率是 10 Hz。
        # EN: Run control_step every 0.1 seconds, targeting 10 Hz.
        self.DWA_time = self.create_timer(0.1,self.DWA_control_step)

        # 创建订阅者
        # 参数1：消息类型
        # 参数2：话题名称 (/counter)
        # 参数3：回调函数 (self.listener_callback)
        # 参数4：队列大小 (10)
        self.scan_sub = self.create_subscription(
            LaserScan,
            LiDAR_Topic,
            self.on_scan,
            qos_profile_sensor_data,
        )
        
        self.odom_sub = self.create_subscription(
            Odometry,
            Odometry_Topic,
            self.on_odom,
            qos_profile_sensor_data,
        )


        # 打印初始化完成信息
        self.get_logger().info('订阅者节点已启动，等待消息...')

    # ZH:DWA执行器
    # EH:DWA actuator
    def DWA_control_step(self):
        """
        ZH: 每 0.1 秒执行一次 DWA_control_step，目标频率是 10 Hz。
        EN: Run DWA_control_step every 0.1 seconds, targeting 10 Hz.
        """
        if self.latest_odom is None :
            self.get_logger().info(
                f'can not receive odometry'
                )
            return
        if self.latest_scan is None :
            self.get_logger().info(
                f'can not receive lidar scan'
                )
            return

        
        twist = self.latest_odom.twist.twist
        v_x = twist.linear.x
        v_w = twist.angular.z
        lidar_scan = self.latest_scan.ranges

        # ZH:判断是否收到雷达数据
        # EH:Determine whether radar data has been received
        self.get_logger().info(
            f'scan points = {len(lidar_scan)},'
            f'v={v_x:.2f} m/s, w={v_w:.2f} rad/s'
            )

        self.latest_pose = self.get_map_pose()
        sample = self.dynamic_window(v_x,v_w)

        # ZH:判断是否收到位置数据
        # EH:Check if position data has been received
        if self.latest_pose is None :
            self.get_logger().info(
                f'pose error'
                )
            return

        # ZH:判断是否测算出动态范围
        # EH:Determine whether the dynamic range has been calculated
        if sample is None :
            self.get_logger().info(
                f'dynamic_window error'
                )
            return

        self.getlogger().info(
            f'pose = {self.latest_pose},',
            f'v_window = {sample[0]:.2f},',
            f'w_window = {sample[1]:.2f}'
        )
        
    def on_scan(self, msg):
        # ZH:提取消息数据
        # EN:Cancel the message data
        self.latest_scan = msg


    def on_odom(self, msg):
        # ZH:提取消息数据
        # EN:Cancel the message data
        self.latest_odom = msg


    def get_map_pose(self):
        try:
            # ZH: 查询 base_link 在 map 中的最新可用位姿。
            # EN: Query the latest available base_link pose in map.
            transform = self.tf_buffer.lookup_transform(
                'map', 'base_link', Time()
            )
        except TransformException:
            # ZH: TF 尚未可用，本轮暂不计算轨迹。
            # EN: Skip this cycle while TF is unavailable.
            return None

        position = transform.transform.translation
        q = transform.transform.rotation

        # ZH: 将四元数转换为偏航角，单位为弧度。
        # EN: Convert the quaternion to yaw in radians.
        yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z),
        )
        return position.x, position.y, yaw


    # CH:计算在t=0.1秒时小车的线速度和角速度范围
    # EN:Calculate the range of the linear velocity and angular velocity of the car at t = 0.1 seconds.
    def dynamic_window(self,v,w):
        # v = self.latest_odom.twist.twist.linear.x
        # w = self.latest_odom.twist.twist.angular.z
        t = 0.1

        # CH:线速度：假设不允许倒车
        # EN:Linear velocity: Assuming that reversing is not allowed
        v_min = max(0.0, v + self.v_a_min * t)
        v_max = min(self.v_max, v + self.v_a_max * t)

        # CH:角速度：允许左转和右转
        # EN:Angular velocity: Allows left turn and right turn
        w_min = max(self.w_min, w + self.w_a_min * t)
        w_max = min(self.w_max, w + self.w_a_max * t)
        
        # CH:对速度采样十个等距点
        # EN:Take ten equally spaced points for speed sampling
        v_samples = np.linspace(v_min, v_max, 10)
        w_samples = np.linspace(w_min, w_max,10)

        return v_samples, w_samples

        # for v_point in v_samples:
        #     for w_point in w_samples:
        #         predict_trajectory(self,self.pose, v_point, w_point)



    # def predict_trajectory(self,pose,v,w):






 
def main(args=None):
    # CH: 初始化 ROS，并创建真正包含订阅和定时器的节点。
    # EN: Initialise ROS and create the node containing subscriptions and timer.
    rclpy.init(args=args)

    node = DWA_run()    


    try:
        # CH:循环运行节点
        # EH:Loop-running node
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
    
if __name__ == '__main__':
    main()