"""Estimate a camera-relative surface point from an aligned depth image and box."""
import math

import cv2
import numpy as np


TORSO = (0.25, 0.25, 0.75, 0.60)
DEPTH_LIMITS_M = (0.3, 10.0)
MIN_PIXELS = 12
MIN_VALID_FRACTION = 0.30
MIN_SUPPORT_FRACTION = 0.25
MODE_GAP_M = 0.10
COMPETITOR_RATIO = 0.67


def torso_bounds(box, width, height):
    """Return a clipped [left, top, right, bottom) pixel ROI."""
    x1, y1, x2, y2 = box
    if not all(math.isfinite(value) for value in box) or x2 <= x1 or y2 <= y1:
        return 0, 0, 0, 0
    left = math.floor(x1 + (x2 - x1) * TORSO[0])
    top = math.floor(y1 + (y2 - y1) * TORSO[1])
    right = math.ceil(x1 + (x2 - x1) * TORSO[2])
    bottom = math.ceil(y1 + (y2 - y1) * TORSO[3])
    return max(0, left), max(0, top), min(width, right), min(height, bottom)


def project_pixel(u, v, z, intrinsics):
    fx, fy, cx, cy = intrinsics
    return [(u + 0.5 - cx) * z / fx, (v + 0.5 - cy) * z / fy, z]


def _estimate_result(pixels, samples, bounds, intrinsics, diagnostics):
    left, top, right, bottom = bounds
    z = float(np.median(samples))
    # Pick a real support pixel near both the spatial and depth medians.
    central = np.median(pixels, axis=0)
    near_depth = np.flatnonzero(np.abs(samples - z) <= 0.02)
    if not near_depth.size:
        near_depth = np.array([int(np.argmin(np.abs(samples - z)))])
    index = near_depth[np.argmin(np.sum((pixels[near_depth] - central) ** 2, axis=1))]
    v, u = (int(value) for value in pixels[index])
    u, v = u + left, v + top
    point = project_pixel(u, v, z, intrinsics)
    return dict(diagnostics, status='valid', pixel=[u, v], xyz_m=point,
                depth_z_m=z, range_m=math.hypot(*point), support_pixels=int(samples.size),
                support_fraction=float(samples.size / ((right - left) * (bottom - top))))


def estimate_depth(depth, box, intrinsics, *, guarded=True):
    """Select a central connected depth mode, or compute the unguarded median baseline."""
    bounds = torso_bounds(box, depth.shape[1], depth.shape[0])
    left, top, right, bottom = bounds
    diagnostics = {'roi': list(bounds), 'valid_fraction': 0.0}
    if right <= left or bottom <= top:
        return dict(diagnostics, status='empty_roi')
    roi = depth[top:bottom, left:right]
    low, high = DEPTH_LIMITS_M
    pixels = np.argwhere(np.isfinite(roi) & (roi >= low) & (roi <= high))
    samples = roi[tuple(pixels.T)]
    diagnostics['valid_fraction'] = float(samples.size / roi.size)
    if samples.size < MIN_PIXELS or diagnostics['valid_fraction'] < MIN_VALID_FRACTION:
        return dict(diagnostics, status='insufficient_depth')
    if not guarded:
        return _estimate_result(pixels, samples, bounds, intrinsics, diagnostics)

    sorted_indices = np.argsort(samples)
    gaps = np.flatnonzero(np.diff(samples[sorted_indices]) > MODE_GAP_M) + 1
    center = (np.asarray(roi.shape) - 1) / 2
    radius = np.maximum(center, 1)
    candidates = []
    for group in np.split(sorted_indices, gaps):
        if group.size < MIN_PIXELS:
            continue
        median = np.median(samples[group])
        band = np.clip(0.04 * median, 0.08, 0.20)
        group = group[np.abs(samples[group] - median) <= band]
        mask = np.zeros(roi.shape, dtype=np.uint8)
        mask[tuple(pixels[group].T)] = 1
        _, components = cv2.connectedComponents(mask, connectivity=8)
        component_ids = components[tuple(pixels[group].T)]
        for component_id in np.unique(component_ids):
            members = group[component_ids == component_id]
            if members.size < MIN_PIXELS or members.size < MIN_SUPPORT_FRACTION * roi.size:
                continue
            squared_radius = np.sum(((pixels[members] - center) / radius) ** 2, axis=1)
            weight = float(np.sum(1 / (1 + 4 * squared_radius)))
            candidates.append((weight, float(np.median(samples[members])), members))
    if not candidates:
        return dict(diagnostics, status='no_supported_mode')
    candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    weight, z, members = candidates[0]
    if any(other_weight >= weight * COMPETITOR_RATIO and abs(other_z - z) > 0.20
           for other_weight, other_z, _ in candidates[1:]):
        return dict(diagnostics, status='ambiguous_depth')
    return _estimate_result(pixels[members], samples[members], bounds, intrinsics, diagnostics)
