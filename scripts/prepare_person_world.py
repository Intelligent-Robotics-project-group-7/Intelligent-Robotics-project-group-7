"""Generate evaluation overrides; never edit installed robot packages."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from ament_index_python.packages import get_package_share_directory

ROOT = Path(__file__).resolve().parents[1]


def load_settings(phase=2):
    config = json.loads((ROOT / 'config/person_scenarios.json').read_text())
    if phase == 3:
        depth_config = json.loads((ROOT / 'config/depth_scenarios.json').read_text())
        config['cases'] = depth_config.pop('additional_cases') + config['cases']
        config.update(depth_config)
    return config


def add_label(model, number):
    label = ET.SubElement(model, 'plugin', {'filename': 'gz-sim-label-system', 'name': 'gz::sim::systems::Label'})
    ET.SubElement(label, 'label').text = str(number)


def add_box(world, name, pose, size, color):
    model = ET.SubElement(world, 'model', {'name': name})
    ET.SubElement(model, 'static').text = 'true'
    ET.SubElement(model, 'pose').text = pose
    link = ET.SubElement(model, 'link', {'name': 'link'})
    visual = ET.SubElement(link, 'visual', {'name': 'visual'})
    geometry = ET.SubElement(visual, 'geometry')
    box = ET.SubElement(geometry, 'box')
    ET.SubElement(box, 'size').text = size
    material = ET.SubElement(visual, 'material')
    ET.SubElement(material, 'ambient').text = color
    ET.SubElement(material, 'diffuse').text = color
    return model


def generate(case_id, phase=2):
    config = load_settings(phase)
    case = next(c for c in config['cases'] if c['id'] == case_id)
    dest = ROOT / f'downloads/phase{phase}/generated' / case_id
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
        add_label(person, actor_spec['label'])
        world.append(person)
    if case.get('occluder'):
        occluder = case['occluder'] if isinstance(case['occluder'], dict) else {}
        model = add_box(world, 'occluder', occluder.get('pose', '2.5 0 0.55 0 0 0'),
                        occluder.get('size', '0.2 0.45 1.1'), '0.1 0.2 0.5 1')
        if phase == 3:
            add_label(model, 21)
    if case['category'] == 'plane':
        plane = add_box(world, 'depth_plane', f"{case['distance_m'] - 0.04} 0 0.65 0 0 0",
                        '0.02 1.4 1.2', '0.9 0.35 0.05 1')
        add_label(plane, 30)
    sdf.write(dest / 'world.sdf', encoding='unicode', xml_declaration=True)
    return dest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('case', nargs='?')
    parser.add_argument('--phase', type=int, choices=(2, 3), default=2)
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    if args.list:
        print('\n'.join(case['id'] for case in load_settings(args.phase)['cases']))
    elif args.case:
        print(generate(args.case, args.phase))
    else:
        parser.error('Specify a case or --list')
