"""Independent CPU geometry for scoring Gazebo RGB-D measurements."""
import math
import xml.etree.ElementTree as ET

import numpy as np


# Columns are the optical axes in the Gazebo camera-link frame.
LINK_FROM_OPTICAL = np.array([[0, 0, 1], [-1, 0, 0], [0, -1, 0]])


def pose_transform(pose):
    origin = np.array(pose[:3], dtype=float)
    q = np.array(pose[3:], dtype=float)
    x, y, z, w = q / np.linalg.norm(q)
    rotation = np.array([
        [1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
        [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
        [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)],
    ])
    return origin, rotation


def camera_pose(poses):
    root_origin, root_rotation = pose_transform(poses['turtlebot4'])
    link_origin, link_rotation = pose_transform(poses['oakd_rgb_camera_frame'])
    return root_origin + root_rotation @ link_origin, root_rotation @ link_rotation @ LINK_FROM_OPTICAL


def simulator_intrinsics(path):
    sensor = ET.parse(path).find(".//sensor[@name='rgbd_camera']")
    pose = sensor.findtext('pose', '0 0 0 0 0 0')
    if any(float(value) != 0 for value in pose.split()):
        raise ValueError('The geometry evaluator expects the RGB-D sensor at its link origin')
    camera = sensor.find('camera')
    width, height = int(camera.findtext('image/width')), int(camera.findtext('image/height'))
    focal = width / (2 * math.tan(float(camera.findtext('horizontal_fov')) / 2))
    return (height, width), (focal, focal, width / 2, height / 2)


def pixel_rays(shape, intrinsics):
    fx, fy, cx, cy = intrinsics
    v, u = np.indices(shape, dtype=float)
    return np.stack(((u + 0.5 - cx) / fx, (v + 0.5 - cy) / fy, np.ones(shape)), axis=-1)


def load_obj(path):
    vertices, triangles = [], []
    for line in path.read_text().splitlines():
        parts = line.split()
        if parts and parts[0] == 'v':
            vertices.append([float(value) for value in parts[1:4]])
        elif parts and parts[0] == 'f':
            face = [int(value.split('/')[0]) for value in parts[1:]]
            face = [index - 1 if index > 0 else len(vertices) + index for index in face]
            triangles.extend((face[0], face[i], face[i+1]) for i in range(1, len(face)-1))
    if not vertices or not triangles:
        raise ValueError('Expected a nonempty OBJ visual mesh')
    return np.array(vertices), np.array(triangles, dtype=int)


def rasterize_mesh(vertices, faces, shape, intrinsics):
    """Intersect pixel-centre rays with projected triangles using inverse-Z interpolation."""
    height, width = shape
    fx, fy, cx, cy = intrinsics
    depth = np.full(shape, np.inf)
    z = vertices[:, 2]
    if np.any(z <= 0):
        raise ValueError('Test mesh crosses the camera plane')
    u = vertices[:, 0] * fx / z + cx
    v = vertices[:, 1] * fy / z + cy
    for face in faces:
        x, y = u[face], v[face]
        left = max(0, math.ceil(x.min() - 0.5))
        right = min(width - 1, math.floor(x.max() - 0.5))
        top = max(0, math.ceil(y.min() - 0.5))
        bottom = min(height - 1, math.floor(y.max() - 0.5))
        if right < left or bottom < top:
            continue
        a = x[0] - x[2], y[0] - y[2]
        b = x[1] - x[2], y[1] - y[2]
        determinant = a[0] * b[1] - a[1] * b[0]
        if abs(determinant) < 1e-12:
            continue
        xx = np.arange(left, right + 1)[None, :] + 0.5 - x[2]
        yy = np.arange(top, bottom + 1)[:, None] + 0.5 - y[2]
        wa = (b[1] * xx - b[0] * yy) / determinant
        wb = (a[0] * yy - a[1] * xx) / determinant
        wc = 1 - wa - wb
        inside = (wa >= 0) & (wb >= 0) & (wc >= 0)
        tile = depth[top:bottom + 1, left:right + 1]
        if np.any(inside):
            za, zb, zc = z[face]
            intersection = 1 / (wa[inside] / za + wb[inside] / zb + wc[inside] / zc)
            tile[inside] = np.minimum(tile[inside], intersection)
    return depth


def plane_depth(rays, camera, plane, thickness):
    origin, rotation = camera
    center, plane_rotation = pose_transform(plane)
    normal = plane_rotation[:, 0]
    face = center - thickness / 2 * normal
    return (normal @ (face - origin)) / ((rays @ rotation.T) @ normal)


def person_surface(mesh, actor_pose, camera, rays, intrinsics, labels, label, config):
    """Locate the visible torso surface in the actor's fixed local height band."""
    vertices, faces = mesh
    actor_origin, actor_rotation = pose_transform(actor_pose)
    camera_origin, camera_rotation = camera
    world = vertices @ actor_rotation.T + actor_origin
    optical = (world - camera_origin) @ camera_rotation
    hit_depth = rasterize_mesh(optical, faces, labels.shape, intrinsics)
    hit = np.isfinite(hit_depth)
    visible = labels == label
    overlap = float(np.count_nonzero(visible & hit) / np.count_nonzero(visible))
    points = rays[hit] * hit_depth[hit, None]
    local = (points @ camera_rotation.T + camera_origin - actor_origin) @ actor_rotation
    bottom, top = np.min(vertices[:, 2]), np.max(vertices[:, 2])
    torso_band = (local[:, 2] >= bottom + 0.45 * (top - bottom)) & (local[:, 2] <= bottom + 0.75 * (top - bottom))
    torso = np.zeros(labels.shape, dtype=bool)
    torso[hit] = torso_band
    blockers = (labels == 21) | ((labels >= 11) & (labels <= 12) & (labels != label))
    torso_size = np.count_nonzero(torso)
    obstruction = float(np.count_nonzero(torso & blockers) / torso_size) if torso_size else 0.0
    visible_torso = torso & visible
    count = np.count_nonzero(visible_torso)
    reference = None
    if (count >= config['minimum_torso_truth_pixels']
            and overlap >= config['minimum_truth_projection_coverage']):
        reference = np.median(rays[visible_torso] * hit_depth[visible_torso, None], axis=0).tolist()
    return {'xyz_m': reference, 'torso_pixels': int(count), 'projection_coverage': overlap,
            'torso_obstructed_fraction': obstruction}, hit_depth
