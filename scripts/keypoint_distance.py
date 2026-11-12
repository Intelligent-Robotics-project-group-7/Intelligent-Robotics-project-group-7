"""Range one person's high-confidence pose nodes using an aligned depth image."""
import math

import numpy as np

# Kept as a compatibility parameter so stale callers fail explicitly instead of
# silently running the retired anatomical preference.
SELECTION_POLICIES = ('all_valid',)


def measure_keypoints(depth_m, keypoints, k, threshold=.7, min_points=3,
                      outlier_tolerance_m=.5, outlier_mad_scale=3., selection_policy='all_valid'):
    """keypoints contains (id, u, v, confidence); average valid nodes equally.

    depth_m is optical Z in metres. distance_m is the mean of the nodes'
    Euclidean ranges, while position_m is their 3D centroid. They differ.
    All surviving nodes are averaged without anatomical preference.
    """
    if not math.isfinite(threshold) or not 0 <= threshold <= 1 or min_points < 1:
        raise ValueError('invalid_keypoint_parameters')
    if not all(math.isfinite(v) and v > 0 for v in (outlier_tolerance_m, outlier_mad_scale)):
        raise ValueError('invalid_depth_outlier_parameters')
    if selection_policy not in SELECTION_POLICIES:
        raise ValueError('invalid_selection_policy')
    if depth_m.ndim != 2:
        raise ValueError('invalid_depth_shape')
    fx, fy, cx, cy = k[0], k[4], k[2], k[5]
    if not all(math.isfinite(v) for v in (fx, fy, cx, cy)) or fx <= 0 or fy <= 0:
        raise ValueError('invalid_camera_intrinsics')
    height, width = depth_m.shape
    samples = []
    for node_id, u, v, confidence in keypoints:
        if not all(math.isfinite(value) for value in (u, v, confidence)):
            continue
        if not threshold <= confidence <= 1 or not (0 <= u < width and 0 <= v < height):
            continue
        pixel_u, pixel_v = min(width-1, int(u+.5)), min(height-1, int(v+.5))
        depth = float(depth_m[pixel_v, pixel_u])
        if not math.isfinite(depth) or depth <= 0:
            continue
        x, y, z = depth, -(pixel_u-cx)*depth/fx, -(pixel_v-cy)*depth/fy
        samples.append({'id': int(node_id), 'score': float(confidence),
                        'sample_pixel': {'u': pixel_u, 'v': pixel_v}, 'depth_m': depth,
                        'position_m': {'x': x, 'y': y, 'z': z},
                        'distance_m': math.sqrt(x*x+y*y+z*z),
                        'ground_distance_m': math.hypot(x, y)})
    candidates = samples
    rejected = []
    median = gate = None
    if candidates:
        depths = np.array([p['depth_m'] for p in candidates])
        median = float(np.median(depths))
        mad = float(np.median(np.abs(depths-median)))
        gate = max(outlier_tolerance_m, outlier_mad_scale * 1.4826 * mad)
        # Use optical Z so limb position within the image does not itself cause rejection.
        samples = [p for p in candidates if abs(p['depth_m']-median) <= gate]
        rejected = [dict(p, reason='depth_outlier') for p in candidates if abs(p['depth_m']-median) > gate]
    eligible = samples
    result = {'method': 'keypoint_mean', 'keypoint_threshold': threshold,
              'selection_policy': 'all_valid', 'selected_region': 'all_valid', 'selection_trace': [],
              'eligible_count': len(eligible), 'eligible_samples': eligible,
              'unused_count': 0, 'unused_samples': [],
              'candidate_count': len(candidates), 'rejected_count': len(rejected),
              'rejected_samples': rejected, 'median_depth_m': median, 'outlier_gate_m': gate,
              'outlier_tolerance_m': outlier_tolerance_m, 'outlier_mad_scale': outlier_mad_scale,
              'minimum_keypoints': min_points, 'sample_count': len(samples), 'samples': samples,
              'valid': len(samples) >= min_points}
    if not result['valid']:
        result['reason'] = 'insufficient_valid_keypoint_depths'
        return result
    position = {axis: float(np.mean([p['position_m'][axis] for p in samples])) for axis in ('x', 'y', 'z')}
    yaw = math.atan2(position['y'], position['x'])
    result.update({'position_m': position,
                   'depth_m': float(np.mean([p['depth_m'] for p in samples])),
                   'distance_m': float(np.mean([p['distance_m'] for p in samples])),
                   'ground_distance_m': float(np.mean([p['ground_distance_m'] for p in samples])),
                   'centroid_distance_m': math.sqrt(sum(v*v for v in position.values())),
                   'turn_yaw_rad': yaw, 'turn_yaw_deg': math.degrees(yaw)})
    return result
