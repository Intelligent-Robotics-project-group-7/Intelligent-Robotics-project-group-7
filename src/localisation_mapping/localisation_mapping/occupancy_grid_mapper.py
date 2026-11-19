import math

import numpy as np
import rclpy
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import (DurabilityPolicy, QoSProfile, ReliabilityPolicy,
                       qos_profile_sensor_data)
from rclpy.time import Time

from sensor_msgs.msg import LaserScan
from nav_msgs.msg import OccupancyGrid

from tf2_ros import Buffer, TransformListener, TransformException


class OccupancyGridMapper(Node):

    def __init__(self):
        super().__init__('occupancy_grid_mapper')

        def declare(name, default):
            self.declare_parameter(
                name, default, ParameterDescriptor(dynamic_typing=True))

        declare('scan_topic', '/scan')
        declare('map_topic', '/custom_map')
        declare('frame', 'map')            
        declare('resolution', 0.1)        
        declare('width', 300)              
        declare('height', 300)             
        declare('origin_x', -15.0)         
        declare('origin_y', -15.0)
        declare('beam_stride', 4)          
        declare('publish_period', 1.0)     
        declare('max_range', 12.0)        
        declare('tf_timeout', 0.2)         
        declare('clear_max_range', True)   

        def param(name):
            return self.get_parameter(name).value

        self.frame = str(param('frame'))
        self.resolution = float(param('resolution'))
        self.width = int(param('width'))
        self.height = int(param('height'))
        self.origin_x = float(param('origin_x'))
        self.origin_y = float(param('origin_y'))
        self.beam_stride = max(1, int(param('beam_stride')))
        self.max_range = float(param('max_range'))
        self.tf_timeout = Duration(seconds=float(param('tf_timeout')))
        self.clear_max_range = bool(param('clear_max_range'))

        if self.resolution <= 0 or self.width <= 0 or self.height <= 0:
            raise ValueError('resolution, width and height must be positive')
        if self.max_range <= 0 or not math.isfinite(self.max_range):
            raise ValueError('max_range must be a positive finite number')

        self.processed_scans = 0

        
        self.log_odds = np.zeros((self.height, self.width), dtype=np.float32)
        self.observed = np.zeros((self.height, self.width), dtype=bool)

        self.free_update = math.log(0.3 / 0.7)
        self.occupied_update = math.log(0.7 / 0.3)
        self.min_log_odds = -5.0
        self.max_log_odds = 5.0

       
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(
            self.tf_buffer, self, spin_thread=True)

        self.scan_subscriber = self.create_subscription(
            LaserScan,
            str(param('scan_topic')),
            self.scan_callback,
            qos_profile_sensor_data
        )

        
        map_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE
        )
        self.map_publisher = self.create_publisher(
            OccupancyGrid, str(param('map_topic')), map_qos)

        self.map_timer = self.create_timer(
            float(param('publish_period')), self.publish_map)

        self.get_logger().info(
            f'Occupancy grid mapper started (frame: {self.frame}, '
            f'{self.width}x{self.height} cells @ {self.resolution} m, '
            f'max_range {self.max_range} m)'
        )

    def world_to_grid(self, x, y):
        gx = int(math.floor((x - self.origin_x) / self.resolution))
        gy = int(math.floor((y - self.origin_y) / self.resolution))
        return gx, gy

    def inside_map(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height

    def ray_trace(self, x0, y0, x1, y1):
        """Cells crossed by a ray (Bresenham), start and end included."""
        cells = []
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        step_x = 1 if x0 < x1 else -1
        step_y = 1 if y0 < y1 else -1
        error = dx - dy

        while True:
            cells.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * error
            if e2 > -dy:
                error -= dy
                x0 += step_x
            if e2 < dx:
                error += dx
                y0 += step_y
        return cells

    def update_cells(self, cells, update):
        """Add `update` to the log-odds of many (x, y) cells at once."""
        if len(cells) == 0:
            return

        cells = np.asarray(cells, dtype=np.int64)
        xs, ys = cells[:, 0], cells[:, 1]

        inside = (xs >= 0) & (xs < self.width) & (ys >= 0) & (ys < self.height)
        xs, ys = xs[inside], ys[inside]
        if xs.size == 0:
            return

        np.add.at(self.log_odds, (ys, xs), update)
        self.log_odds[ys, xs] = np.clip(
            self.log_odds[ys, xs], self.min_log_odds, self.max_log_odds)
        self.observed[ys, xs] = True

    def scan_callback(self, scan):
        try:
            
            transform = self.tf_buffer.lookup_transform(
                self.frame,
                scan.header.frame_id,
                Time(),
                timeout=self.tf_timeout
            )
        except TransformException as exc:
            self.get_logger().warn(
                f'No TF {self.frame} -> {scan.header.frame_id} at scan time: '
                f'{exc} (is use_sim_time:=true set in simulation?)',
                throttle_duration_sec=5.0
            )
            return

        sensor_x = transform.transform.translation.x
        sensor_y = transform.transform.translation.y

        q = transform.transform.rotation
        sensor_yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        )

        start_x, start_y = self.world_to_grid(sensor_x, sensor_y)
        if not self.inside_map(start_x, start_y):
            self.get_logger().warn(
                'Sensor is outside the map; ignoring scan',
                throttle_duration_sec=5.0
            )
            return

       
        sensor_max = scan.range_max if math.isfinite(scan.range_max) else self.max_range
        r_max = min(sensor_max, self.max_range)

        free_cells = []
        occupied_cells = []

        for i in range(0, len(scan.ranges), self.beam_stride):
            distance = scan.ranges[i]

            if math.isnan(distance) or distance == -math.inf:
                continue

            hit_obstacle = math.isfinite(distance)

            if hit_obstacle and distance < scan.range_min:
                continue

          
            if hit_obstacle and distance > r_max:
                hit_obstacle = False

            if not hit_obstacle:
                distance = r_max

            angle = sensor_yaw + scan.angle_min + i * scan.angle_increment

            end_x = sensor_x + distance * math.cos(angle)
            end_y = sensor_y + distance * math.sin(angle)
            grid_end_x, grid_end_y = self.world_to_grid(end_x, end_y)

            cells = self.ray_trace(start_x, start_y, grid_end_x, grid_end_y)

            if hit_obstacle:
                if len(cells) > 1:
                    free_cells.extend(cells[:-1])
                occupied_cells.append(cells[-1])
            else:
                if self.clear_max_range:
                    free_cells.extend(cells)
                else:
                    free_cells.extend(cells[:-1])

        occupied = set(occupied_cells)
        free = set(free_cells) - occupied
        self.update_cells(list(free), self.free_update)
        self.update_cells(list(occupied), self.occupied_update)

        self.processed_scans += 1
        if self.processed_scans % 100 == 0:
            self.get_logger().info(
                f'Processed {self.processed_scans} LiDAR scans')

  
    def publish_map(self):
        msg = OccupancyGrid()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame

        msg.info.resolution = self.resolution
        msg.info.width = self.width
        msg.info.height = self.height
        msg.info.origin.position.x = self.origin_x
        msg.info.origin.position.y = self.origin_y
        msg.info.origin.orientation.w = 1.0

        probabilities = 1.0 / (1.0 + np.exp(-self.log_odds))
        occupancy = np.rint(probabilities * 100).astype(np.int8)
        occupancy[~self.observed] = -1

        msg.data = occupancy.flatten().tolist()
        self.map_publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = OccupancyGridMapper()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()