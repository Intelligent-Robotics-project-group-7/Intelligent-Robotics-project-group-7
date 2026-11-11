import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from depth_estimation import estimate_depth, project_pixel
from depth_truth_geometry import plane_depth, pixel_rays, rasterize_mesh


INTRINSICS = (50.0, 50.0, 20.0, 20.0)
BOX = (0, 0, 40, 40)


def test_invalid_depth_does_not_return_a_distance():
    depth = np.full((40, 40), np.nan, dtype=np.float32)
    depth[11:12, 11:13] = [0, np.inf]
    result = estimate_depth(depth, BOX, INTRINSICS)
    assert result['status'] == 'insufficient_depth'
    assert 'depth_z_m' not in result


def test_centered_connected_surface_wins_over_background():
    depth = np.full((40, 40), 6, dtype=np.float32)
    depth[10:24, 13:27] = 2
    result = estimate_depth(depth, BOX, INTRINSICS)
    assert result['depth_z_m'] == 2
    u, v = result['pixel']
    assert depth[v, u] == 2
    assert result['range_m'] >= result['depth_z_m']


def test_two_equally_supported_surfaces_are_rejected():
    depth = np.full((40, 40), 4, dtype=np.float32)
    depth[:, :20] = 2
    assert estimate_depth(depth, BOX, INTRINSICS)['status'] == 'ambiguous_depth'


def test_projection_and_analytic_plane_agree_off_axis():
    rays = pixel_rays((40, 40), INTRINSICS)
    depths = plane_depth(rays, (np.zeros(3), np.eye(3)), [0, 0, 2.01, 0, -(2**-.5), 0, 2**-.5], 0.02)
    assert depths[10, 30] == pytest.approx(2)
    assert project_pixel(30, 10, 2, INTRINSICS) == pytest.approx([0.42, -0.38, 2])


def test_mesh_rasterizer_uses_perspective_correct_depth():
    # All three vertices are on the slanted plane z = 2 + x.
    vertices = np.array([[-0.5, -0.5, 1.5], [0.8, -0.5, 2.8], [0, 0.7, 2]])
    depth = rasterize_mesh(vertices, np.array([[0, 1, 2]]), (40, 40), INTRINSICS)
    u, v = 23, 20
    assert depth[v, u] == pytest.approx(2 / (1 - (u + 0.5 - 20) / 50))
