"""Generate evaluation overrides; never edit installed robot packages."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from ament_index_python.packages import get_package_share_directory

ROOT = Path(__file__).resolve().parents[1]


def generate(case_id):
    config = json.loads((ROOT / 'config/person_scenarios.json').read_text())
    case = next(c for c in config['cases'] if c['id'] == case_id)
    dest = ROOT / 'downloads/phase2/generated' / case_id
    dest.mkdir(parents=True, exist_ok=True)
    desc = Path(get_package_share_directory('turtlebot4_description'))
    xml = subprocess.check_output(['xacro', str(desc / 'urdf/standard/turtlebot4.urdf.xacro'),
                                   'gazebo:=ignition', 'namespace:='], text=True)
    robot = ET.fromstring(xml)
    native = robot.find(".//sensor[@name='rgbd_camera']")
    native.find('update_rate').text = str(config['sensor_hz'])
    # Co-located optical rendering reference. Labels never enter the detector.
    parent = next(g for g in robot.findall('gazebo') if native in list(g))
    truth = ET.SubElement(parent, 'sensor', {'name': 'ground_truth_camera', 'type': 'segmentation'})
    camera = copy.deepcopy(native.find('camera'))
    ET.SubElement(camera, 'segmentation_type').text = 'semantic'
    truth.append(camera)
    ET.SubElement(truth, 'always_on').text = '1'
    ET.SubElement(truth, 'update_rate').text = str(config['sensor_hz'])
    ET.SubElement(truth, 'topic').text = '/evaluation/semantic'
    ET.ElementTree(robot).write(dest / 'robot.urdf', encoding='unicode', xml_declaration=True)

    sdf = ET.parse(ROOT / 'worlds/camera_smoke.sdf')
    world = sdf.getroot().find('world')
    world.set('name', 'person_eval')
    for model in list(world.findall('model')):
        if model.get('name') == 'depth_reference':
            world.remove(model)
    for index, actor_spec in enumerate(case['actors'], 1):
        person = ET.parse(ROOT / 'downloads/phase2/Scrubs/model.sdf').getroot().find('model')
        person.set('name', f'person_{index}')
        _, x, y, yaw = actor_spec['waypoints'][0]
        pose = person.find('pose')
        if pose is None:
            pose = ET.SubElement(person, 'pose')
        pose.text = f'{x} {y} 0 0 0 {yaw}'
        for link in person.findall('link'):
            for collision in list(link.findall('collision')):
                link.remove(collision)  # visual-only people; not a physical collision model
        label = ET.SubElement(person, 'plugin', {'filename': 'gz-sim-label-system', 'name': 'gz::sim::systems::Label'})
        ET.SubElement(label, 'label').text = str(actor_spec['label'])
        world.append(person)
    if case.get('occluder'):
        model = ET.SubElement(world, 'model', {'name': 'occluder'})
        ET.SubElement(model, 'static').text = 'true'
        ET.SubElement(model, 'pose').text = '2.5 0 0.55 0 0 0'
        link = ET.SubElement(model, 'link', {'name': 'link'})
        visual = ET.SubElement(link, 'visual', {'name': 'visual'})
        geometry = ET.SubElement(visual, 'geometry')
        box = ET.SubElement(geometry, 'box')
        ET.SubElement(box, 'size').text = '0.2 0.45 1.1'
        material = ET.SubElement(visual, 'material')
        ET.SubElement(material, 'ambient').text = '0.1 0.2 0.5 1'
        ET.SubElement(material, 'diffuse').text = '0.1 0.2 0.5 1'
    sdf.write(dest / 'world.sdf', encoding='unicode', xml_declaration=True)
    return dest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('case')
    args = parser.parse_args()
    print(generate(args.case))
