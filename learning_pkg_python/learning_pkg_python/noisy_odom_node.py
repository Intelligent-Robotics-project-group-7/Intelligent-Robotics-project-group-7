#!/usr/bin/env python3
"""ZH: 带噪速度积分里程计：同时生成位姿、速度、协方差及 odom→base_link。
EN: Noisy velocity-integrated odometry: publish pose, velocity, covariance, and odom-to-base_link TF.

ZH: 输入仅使用轮式里程计的 twist 和时间戳，不读取 Gazebo 真值。
EN: Use only wheel-odometry twist and timestamps as input; do not read Gazebo ground truth.
ZH: 这是一种可控测量噪声模型，不等同于完整的编码器量化或轮胎打滑模型。
EN: This controlled measurement-noise model does not fully model encoder quantization or wheel slip.
"""
import math
import random

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from tf2_ros import TransformBroadcaster


def motion_step(x, y, yaw, covariance, v, w, dt, sigma_v, sigma_w):
    """ZH: 区间内速度保持不变的圆弧积分，以及一阶线性化的噪声协方差传播。
EN: Integrate a constant-velocity arc and propagate noise covariance using first-order linearization."""
    a = w * dt / 2.0
    if abs(a) < 1e-6:
        sinc = 1.0 - a * a / 6.0  # ZH: sin(a)/a 的稳定近似。 | EN: Numerically stable approximation of sin(a)/a near zero.
        dsinc = -a / 3.0
    else:
        sinc = math.sin(a) / a
        dsinc = (a * math.cos(a) - math.sin(a)) / (a * a)
    c, s = math.cos(yaw + a), math.sin(yaw + a)
    dx, dy = v * dt * sinc * c, v * dt * sinc * s
    # ZH: F 是对上一时刻状态 (x,y,yaw) 的雅可比，G 是对输入 (v,w) 的雅可比。 | EN: F is the Jacobian with respect to the previous state (x,y,yaw); G is the Jacobian with respect to inputs (v,w).
    f = [[1.0, 0.0, -dy], [0.0, 1.0, dx], [0.0, 0.0, 1.0]]
    g = [[dt*sinc*c, v*dt*dt/2.0*(dsinc*c-sinc*s)],
         [dt*sinc*s, v*dt*dt/2.0*(dsinc*s+sinc*c)], [0.0, dt]]
    p = [[sum(f[i][k]*covariance[k][l]*f[j][l] for k in range(3) for l in range(3))
          + sum(g[i][k]*g[j][k]*q for k, q in enumerate((sigma_v**2, sigma_w**2)))
          for j in range(3)] for i in range(3)]
    return x+dx, y+dy, math.atan2(math.sin(yaw+w*dt), math.cos(yaw+w*dt)), p


class NoisyOdometry(Node):
    def __init__(self):
        super().__init__('wheel_noise')
        # ZH: 参数可在 config/odom_noise_rescue.yaml 中修改；正式对比时保持相同。 | EN: Edit parameters in config/odom_noise_rescue.yaml; keep them identical across formal comparisons.
        for name, value in [('sigma_v', .01), ('sigma_w', .02), ('bias_v', 0.0),
                            ('bias_w', 0.0), ('seed', 42)]:
            self.declare_parameter(name, value)
        self.sigma_v = float(self.get_parameter('sigma_v').value)
        self.sigma_w = float(self.get_parameter('sigma_w').value)
        self.bias_v = float(self.get_parameter('bias_v').value)
        self.bias_w = float(self.get_parameter('bias_w').value)
        if self.sigma_v < 0 or self.sigma_w < 0:
            raise ValueError('噪声标准差不能为负。')
        self.seed = int(self.get_parameter('seed').value)
        self.reset_state()
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.wheel_pub = self.create_publisher(Odometry, '/wheel/odometry', 10)
        self.tf_pub = TransformBroadcaster(self)
        self.sub = self.create_subscription(
            Odometry, '/wheel/odometry_raw', self.on_raw, qos_profile_sensor_data)
        self.get_logger().info('带噪轮式里程计已启动；/odom 与 TF 使用同一积分状态。')

    def reset_state(self):
        self.rng = random.Random(self.seed)
        self.x = self.y = self.yaw = 0.0  # ZH: 本地 odom 从启动点开始，不是世界绝对坐标。 | EN: Local odometry starts at the node initialization point, rather than an absolute world position.
        self.p = [[1e-6 if i == j else 0.0 for j in range(3)] for i in range(3)]
        self.previous_stamp = None
        self.previous_v = self.previous_w = 0.0

    def on_raw(self, raw):
        stamp = raw.header.stamp.sec + raw.header.stamp.nanosec * 1e-9
        if self.previous_stamp is not None:
            dt = stamp - self.previous_stamp
            if dt < 0.0:
                self.get_logger().warning('检测到仿真时间回跳：重置里程计；定位和导航也需重新初始化。')
                self.reset_state()
            elif dt == 0.0:
                return  # ZH: 重复时间戳不重复积分或抽取噪声。 | EN: Do not integrate again or draw new noise for a duplicate timestamp.
            else:
                self.x, self.y, self.yaw, self.p = motion_step(
                    self.x, self.y, self.yaw, self.p, self.previous_v, self.previous_w,
                    dt, self.sigma_v, self.sigma_w)

        # ZH: 当前含噪测量用于下一段时间的积分，形成真实的累积误差。 | EN: Hold the current noisy measurement over the next interval to produce accumulated integration error.
        v = raw.twist.twist.linear.x + self.bias_v + self.rng.gauss(0, self.sigma_v)
        w = raw.twist.twist.angular.z + self.bias_w + self.rng.gauss(0, self.sigma_w)
        self.previous_stamp, self.previous_v, self.previous_w = stamp, v, w

        out = Odometry()
        out.header.stamp = raw.header.stamp
        out.header.frame_id = 'odom'
        out.child_frame_id = 'base_link'
        out.pose.pose.position.x, out.pose.pose.position.y = self.x, self.y
        out.pose.pose.orientation.z = math.sin(self.yaw/2)
        out.pose.pose.orientation.w = math.cos(self.yaw/2)
        out.twist.twist.linear.x, out.twist.twist.angular.z = v, w
        # ZH: ROS 6×6 协方差按 x,y,z,roll,pitch,yaw 排列；平面状态对应 0,1,5。 | EN: ROS 6-by-6 covariance order is x,y,z,roll,pitch,yaw; planar states occupy indices 0,1,5.
        indices = (0, 1, 5)
        for i in range(3):
            for j in range(3):
                out.pose.covariance[indices[i]*6+indices[j]] = self.p[i][j]
        for i in (2, 3, 4):
            out.pose.covariance[i*6+i] = 1e-6  # ZH: 本模型把离平面运动视为受约束。 | EN: This planar model treats out-of-plane motion as constrained.
        for i in range(6):
            out.twist.covariance[i*6+i] = 1e-6
        out.twist.covariance[0] = self.sigma_v**2
        out.twist.covariance[35] = self.sigma_w**2
        self.odom_pub.publish(out)
        self.wheel_pub.publish(out)

        transform = TransformStamped()
        transform.header = out.header
        transform.child_frame_id = out.child_frame_id
        transform.transform.translation.x = self.x
        transform.transform.translation.y = self.y
        transform.transform.rotation = out.pose.pose.orientation
        self.tf_pub.sendTransform(transform)


def main():
    rclpy.init()
    node = None
    try:
        node = NoisyOdometry()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
