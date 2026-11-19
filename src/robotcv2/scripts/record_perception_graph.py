"""Read-only graph audit: renderer labels must not be an input to the detector."""
import json
from pathlib import Path
import time
import rclpy
from rclpy.node import Node

rclpy.init()
node = Node('perception_graph_audit')
time.sleep(1.5)
topics = ['/oakd/rgb/preview/image_raw', '/evaluation/semantic/labels_map',
          '/yolo/oakd/detections', '/perception/people/detections2d']
report = {'subscriptions': {}, 'all_topics': node.get_topic_names_and_types()}
for topic in topics:
    report['subscriptions'][topic] = [{'node': x.node_name, 'namespace': x.node_namespace, 'type': x.topic_type}
                                      for x in node.get_subscriptions_info_by_topic(topic)]
truth_nodes = report['subscriptions']['/evaluation/semantic/labels_map']
report['detector_subscribed_to_truth'] = any(x['node'] in ('yolo_node', 'person_detection_adapter') for x in truth_nodes)
report['robot_velocity_topics'] = [name for name,types in report['all_topics'] if 'cmd_vel' in name]
target = Path(__file__).resolve().parents[1] / 'evidence/phase2/graph_audit.json'
target.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'detector_subscribed_to_truth':report['detector_subscribed_to_truth'],
                  'robot_velocity_topics':report['robot_velocity_topics']},indent=2))
node.destroy_node()
rclpy.shutdown()
raise SystemExit(1 if report['detector_subscribed_to_truth'] or report['robot_velocity_topics'] else 0)
