import dataclasses

import numpy as np
import pytest

from darts.camera import intrinsics, pose, project
from darts.twin import load_twin


@pytest.fixture(scope="module")
def twin():
    return load_twin()


def test_the_board_centre_projects_to_the_image_centre(twin):
    b = twin.board
    u, v = project(twin, np.array([b.distance_m, 0.0, b.centre_height_m]))
    assert (u, v) == pytest.approx((twin.camera.width_px / 2, twin.camera.height_px / 2), abs=1e-6)


def test_projection_matches_a_hand_computed_pixel(twin):
    """Camera on the board's axis, 2 m away, 1.9 m up: a point 0.1 m to the camera's right and
    0.05 m up lands 0.05 f pixels right and 0.025 f pixels above the centre."""
    t = dataclasses.replace(
        twin,
        board=dataclasses.replace(twin.board, distance_m=2.0, centre_height_m=1.9),
        camera=dataclasses.replace(twin.camera, x_m=0.0, y_m=0.0, z_m=1.9),
    )
    f = 240 / np.tan(np.radians(30))  # fovy 60 deg, 480 px high
    u, v = project(t, np.array([2.0, -0.1, 1.95]))  # camera right is world -y when looking along +x
    assert (u, v) == pytest.approx((320 + 0.05 * f, 240 - 0.025 * f), abs=1e-6)


def test_axes_are_orthonormal_and_right_handed(twin):
    _, axes = pose(twin)
    assert np.allclose(axes.T @ axes, np.eye(3))
    assert np.linalg.det(axes) == pytest.approx(1.0)
