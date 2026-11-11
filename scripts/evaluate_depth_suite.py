"""Score captured ROS outputs against separately computed Gazebo geometry."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import cv2
import numpy as np

from depth_estimation import estimate_depth
from depth_truth_geometry import (camera_pose, load_obj, person_surface, pixel_rays,
                                  plane_depth, simulator_intrinsics)
from detection_metrics import match_frame
from prepare_person_world import load_settings


ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / 'downloads/phase3/capture'
OUTPUT = ROOT / 'evidence/phase3'


def error_stats(values):
    if not values:
        return {'n': 0}
    return {'n': len(values), 'mean_m': float(np.mean(values)), 'std_m': float(np.std(values)),
            'mae_m': float(np.mean(np.abs(values))), 'p95_abs_m': float(np.percentile(np.abs(values), 95))}


def mask_iou(first, second):
    union = np.count_nonzero(first | second)
    return float(np.count_nonzero(first & second) / union) if union else None


def score_plane(row, depth, rgb, labels, rays, pose):
    if pose is None:
        return {'stamp_ns': row['stamp_ns'], 'status': 'missing_pose'}
    reference = plane_depth(rays, pose, row['poses']['depth_plane'], 0.02)
    plate = labels == 30
    height, width = labels.shape
    central = np.s_[height//2-12:height//2+12, width//2-12:width//2+12]
    valid = np.isfinite(depth) & (depth > 0)
    central_plate = plate[central]
    selected = valid[central] & central_plate
    record = {'stamp_ns': row['stamp_ns'], 'reference_pixels': int(np.count_nonzero(central_plate)),
              'valid_pixels': int(np.count_nonzero(selected)), 'status': 'missing_depth_or_plate'}
    if not np.any(selected):
        return record
    expected = float(np.median(reference[central][selected]))
    measured = float(np.median(depth[central][selected]))
    near_plane = valid & (np.abs(depth - reference) < 0.03)
    b, g, r = np.moveaxis(rgb, -1, 0)
    rgb_plate = (r > 40) & (r > 1.3*g) & (r > 1.5*b)
    return dict(record, status='valid', expected_z_m=expected, measured_z_m=measured,
                error_z_m=measured - expected, rgb_plate_iou=mask_iou(rgb_plate, plate),
                depth_plate_iou=mask_iou(near_plane, plate))


def visible_boxes(labels):
    truth = []
    for label in (11, 12):
        v, u = np.where(labels == label)
        if u.size:
            truth.append({'label': label, 'box': [int(u.min()), int(v.min()), int(u.max()+1), int(v.max()+1)]})
    return truth


def assess(estimate, label, labels, reference, mesh_depth, rays):
    if estimate['status'] != 'valid':
        return estimate
    u, v = estimate['pixel']
    actual_label = int(labels[v, u])
    if actual_label == label:
        surface = 'target_person'
    elif actual_label in (11, 12):
        surface = 'other_person'
    elif actual_label == 21:
        surface = 'occluder'
    else:
        surface = 'background'
    result = dict(estimate, surface=surface, selected_label=actual_label)
    point = np.array(estimate['xyz_m'])
    if reference is not None:
        delta = point - reference
        result['torso_z_error_m'] = float(delta[2])
        result['torso_position_error_m'] = float(np.linalg.norm(delta))
    if surface == 'target_person' and mesh_depth is not None and np.isfinite(mesh_depth[v, u]):
        true_z = mesh_depth[v, u]
        result['ray_z_error_m'] = float(point[2] - true_z)
        result['ray_position_error_m'] = float(np.linalg.norm(point - rays[v, u] * true_z))
    return result


def score_people(row, depth, labels, rays, pose, mesh, intrinsics, config):
    truth = visible_boxes(labels)
    boxes = row['boxes']['boxes'] if row['boxes'] else []
    matches = match_frame(truth, [dict(box=item['bbox'], score=item['score']) for item in boxes],
                          config['evaluation_iou'])
    indices = {pair['ground_truth']: pair['prediction'] for pair in matches['matches']}
    output = row['output']
    live = {item['detection_index']: item for item in output['estimates']} if output else {}
    compare = bool(output and output['status'] == 'paired' and row['depth_encoding'] == '32FC1' and row['info'])
    instances = []
    for index, target in enumerate(truth):
        label = target['label']
        actor = f'person_{label - 10}'
        surface, mesh_depth = None, None
        if pose is not None and actor in row['poses']:
            surface, mesh_depth = person_surface(mesh, row['poses'][actor], pose, rays, intrinsics,
                                                 labels, label, config)
        entry = dict(target, truth_surface=surface, detection_matched=index in indices)
        reference = surface['xyz_m'] if surface else None
        if row['depth_encoding'] == '32FC1' and row['info'] and row['depth_frame_id'] == row['info']['frame_id']:
            oracle = estimate_depth(depth, target['box'], row['info']['intrinsics'])
            entry['truth_box'] = assess(oracle, label, labels, reference, mesh_depth, rays)
        else:
            entry['truth_box'] = {'status': 'missing_depth_or_calibration'}
        if index not in indices:
            entry['live'] = {'status': 'detector_miss'}
        else:
            box_index = indices[index]
            fallback = output['status'] if output and output['status'] != 'paired' else 'missing_range_message'
            estimate = live.get(box_index, {'status': fallback})
            entry['live'] = assess(estimate, label, labels, reference, mesh_depth, rays)
            if compare:
                bbox, calibration = boxes[box_index]['bbox'], row['info']['intrinsics']
                replay = estimate_depth(depth, bbox, calibration)
                if any(replay.get(key) != estimate.get(key) for key in ('status', 'pixel', 'depth_z_m')):
                    raise RuntimeError(f"Replay differs from the live result at {row['stamp_ns']}")
                baseline = estimate_depth(depth, bbox, calibration, guarded=False)
                entry['median'] = assess(baseline, label, labels, reference, mesh_depth, rays)
        instances.append(entry)
    return {'stamp_ns': row['stamp_ns'], 'range_frame_status': output['status'] if output else 'missing',
            'pose_delta_ms': (row['pose_stamp_ns'] - row['stamp_ns']) / 1e6 if pose else None,
            'instances': instances, 'unmatched_boxes': matches['fp'],
            'unmatched_numeric_outputs': sum(live.get(i, {}).get('status') == 'valid'
                                             for i in matches['false_positive_indices'])}


def summarize_people(instances, method='live'):
    estimates = [row[method] for row in instances]
    valid = [estimate for estimate in estimates if estimate['status'] == 'valid']
    surfaces = Counter(item['surface'] for item in valid)
    on_target = [item for item in valid if item['surface'] == 'target_person']
    count = len(instances)
    return {'visible_instances': count, 'matched_boxes': sum(row['detection_matched'] for row in instances),
            'torso_references': sum(row['truth_surface'] is not None and row['truth_surface']['xyz_m'] is not None
                                   for row in instances),
            'numeric_outputs': len(valid), 'numeric_output_rate': len(valid)/count if count else None,
            'on_target_outputs': surfaces['target_person'],
            'on_target_output_rate': surfaces['target_person']/count if count else None,
            'wrong_surface_outputs': len(valid) - surfaces['target_person'],
            'surface_counts': dict(surfaces), 'statuses': dict(Counter(item['status'] for item in estimates)),
            'torso_z': error_stats([item['torso_z_error_m'] for item in valid if 'torso_z_error_m' in item]),
            'torso_position': error_stats([item['torso_position_error_m'] for item in valid if 'torso_position_error_m' in item]),
            'on_target_torso_z': error_stats([item['torso_z_error_m'] for item in on_target if 'torso_z_error_m' in item]),
            'on_target_torso_position': error_stats([item['torso_position_error_m'] for item in on_target
                                                   if 'torso_position_error_m' in item]),
            'selected_ray_z': error_stats([item['ray_z_error_m'] for item in valid if 'ray_z_error_m' in item]),
            'selected_ray_position': error_stats([item['ray_position_error_m'] for item in valid if 'ray_position_error_m' in item])}


def save_example(case_id, row, rgb, labels):
    wrong = [(method, item) for method in ('live', 'truth_box') for item in row['instances']
             if item[method].get('surface') in ('other_person', 'occluder', 'background')]
    if not wrong:
        return None
    method, target = wrong[0]
    estimate = target[method]
    preview = cv2.resize(rgb, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    b = np.rint(np.array(estimate.get('bbox', target['box'])) * 2).astype(int)
    cv2.rectangle(preview, tuple(b[:2]), tuple(b[2:]), (100, 230, 80), 2)
    x, y = estimate['pixel']
    cv2.circle(preview, (2*x, 2*y), 6, (20, 20, 255), 2)
    semantic = np.zeros((*labels.shape, 3), dtype=np.uint8)
    semantic[labels == 11] = (25, 180, 255)
    semantic[labels == 12] = (255, 150, 50)
    semantic[labels == 21] = (130, 130, 130)
    semantic = cv2.resize(semantic, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    cv2.circle(semantic, (2*x, 2*y), 6, (20, 20, 255), 2)
    captions = [(preview, f"{case_id} | {method} | Z={estimate['depth_z_m']:.2f} m"),
                (semantic, f"Semantic truth | target {target['label']} | sampled {estimate['selected_label']}")]
    for panel, caption in captions:
        cv2.putText(panel, caption, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, .60, (20, 20, 20), 4)
        cv2.putText(panel, caption, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, .60, (255, 255, 255), 1)
    cv2.imwrite(str(OUTPUT / 'wrong_surface_example.png'), np.hstack((preview, semantic)))
    return {'case': case_id, 'stamp_ns': row['stamp_ns'], 'method': method,
            'target_label': target['label'], 'selected_label': estimate['selected_label'],
            'depth_z_m': estimate['depth_z_m']}


def run(selected):
    config = load_settings(3)
    case_list = [case for case in config['cases'] if not selected or case['id'] in selected]
    if selected and {case['id'] for case in case_list} != set(selected):
        raise ValueError('Unknown case ID')
    mesh = load_obj(ROOT / 'downloads/phase2/Scrubs/meshes/scrubs.obj')
    results, all_rows, ideal, obstructed = [], [], [], []
    OUTPUT.mkdir(parents=True, exist_ok=True)
    example = None
    for case in case_list:
        case_id = case['id']
        capture = json.loads((CAPTURE / f'{case_id}.json').read_text())
        shape, intrinsics = simulator_intrinsics(ROOT / f'downloads/phase3/generated/{case_id}/robot.urdf')
        rays = pixel_rays(shape, intrinsics)
        case_rows = []
        with np.load(CAPTURE / f'{case_id}.npz') as saved:
            depths, images, labels = saved['depth'], saved['rgb'], saved['labels']
        for row, depth, rgb, mask in zip(capture['rows'], depths, images, labels, strict=True):
            pose = None
            if row['poses'] and abs(row['pose_stamp_ns'] - row['stamp_ns']) <= config['maximum_pose_delta_ms'] * 1e6:
                pose = camera_pose(row['poses'])
            if case['category'] == 'plane':
                scored = score_plane(row, depth, rgb, mask, rays, pose)
                scored['pose_delta_ms'] = (row['pose_stamp_ns'] - row['stamp_ns']) / 1e6 if pose else None
            else:
                scored = score_people(row, depth, mask, rays, pose, mesh, intrinsics, config)
                if example is None:
                    example = save_example(case_id, scored, rgb, mask)
            case_rows.append(dict(scored, case=case_id))
        result = {key: value for key, value in capture.items() if key != 'rows'}
        result['category'] = case['category']
        if case['category'] == 'plane':
            valid = [row for row in case_rows if row['status'] == 'valid']
            if len(valid) < 100:
                raise RuntimeError(f'Fewer than 100 measured plane frames: {case_id}')
            result.update(reference_z_m=float(np.mean([row['expected_z_m'] for row in valid])),
                          depth_valid_fraction=sum(row.get('valid_pixels', 0) for row in case_rows) /
                          sum(row.get('reference_pixels', 0) for row in case_rows),
                          depth_z=error_stats([row['error_z_m'] for row in valid]),
                          rgb_plate_iou_mean=float(np.mean([row['rgb_plate_iou'] for row in valid])),
                          depth_plate_iou_mean=float(np.mean([row['depth_plate_iou'] for row in valid])))
        else:
            instances = [item for row in case_rows for item in row['instances']]
            if case['category'] == 'ideal':
                ideal.extend(instances)
            occluded = [item for item in instances if item['truth_surface'] and
                        item['truth_surface']['torso_obstructed_fraction'] >= 0.05]
            obstructed.extend(occluded)
            result.update(summarize_people(instances))
            result['truth_box'] = summarize_people(instances, 'truth_box')
            result['occluded'] = summarize_people(occluded)
            result['unmatched_boxes'] = sum(row['unmatched_boxes'] for row in case_rows)
            result['unmatched_numeric_outputs'] = sum(row['unmatched_numeric_outputs'] for row in case_rows)
        results.append(result)
        all_rows.extend(case_rows)
        print(case_id, result['frames'], result.get('numeric_outputs', result.get('depth_z')), flush=True)

    people = [item for row in all_rows for item in row.get('instances', [])]
    comparable = [item for item in people if 'median' in item]
    comparable_occluded = [item for item in obstructed if 'median' in item]
    report = {'recorded_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'cases': results,
              'overall': summarize_people(people), 'ideal': summarize_people(ideal),
              'occluded': summarize_people(obstructed), 'goal_p95_m': config['position_goal_p95_m'],
              'truth_box': {'overall': summarize_people(people, 'truth_box'),
                            'ideal': summarize_people(ideal, 'truth_box'),
                            'occluded': summarize_people(obstructed, 'truth_box')},
              'same_input_comparison': {name: summarize_people(comparable, name) for name in ('live', 'median')},
              'same_input_occlusion_comparison': {name: summarize_people(comparable_occluded, name)
                                                  for name in ('live', 'median')},
              'maximum_pose_delta_ms': max((abs(row['pose_delta_ms']) for row in all_rows
                                             if row.get('pose_delta_ms') is not None), default=None),
              'wrong_surface_example': example}
    (OUTPUT / 'depth_report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    with (OUTPUT / 'measurements.jsonl').open('w') as stream:
        for row in all_rows:
            stream.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('cases', nargs='*')
    run(parser.parse_args().cases)
