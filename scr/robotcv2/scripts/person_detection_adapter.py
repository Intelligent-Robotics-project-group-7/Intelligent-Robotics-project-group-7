"""Expose the pinned COCO detector through standard vision_msgs, without tracking IDs."""
import math
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose
from yolo_msgs.msg import DetectionArray


class Adapter(Node):
    def __init__(self):
        super().__init__('person_detection_adapter', parameter_overrides=[Parameter('use_sim_time', value=True)])
        self.output = self.create_publisher(Detection2DArray, '/perception/people/detections2d', 10)
        self.input = self.create_subscription(DetectionArray, '/yolo/oakd/detections', self.receive, 10)

    def receive(self, msg):
        result = Detection2DArray()
        result.header = msg.header
        for item in msg.detections:
            if item.class_id != 0 or item.class_name != 'person' or item.score < .25:
                continue
            source = item.bbox
            values = [source.center.position.x, source.center.position.y, source.size.x, source.size.y, item.score]
            if not all(math.isfinite(v) for v in values) or source.size.x <= 0 or source.size.y <= 0:
                continue
            detection = Detection2D()
            detection.header = msg.header
            detection.bbox.center.position.x = source.center.position.x
            detection.bbox.center.position.y = source.center.position.y
            detection.bbox.size_x = source.size.x
            detection.bbox.size_y = source.size.y
            hypothesis = ObjectHypothesisWithPose()
            hypothesis.hypothesis.class_id = 'person'
            hypothesis.hypothesis.score = item.score
            detection.results.append(hypothesis)
            result.detections.append(detection)
        self.output.publish(result)


if __name__ == '__main__':
    rclpy.init()
    node = Adapter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
