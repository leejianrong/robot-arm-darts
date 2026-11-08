import os

import cv2
import mujoco
import numpy as np
import pytest

from darts.board import DOUBLE_IN, DOUBLE_OUT
from darts.camera import project
from darts.detect import EDGE_GROWTH, detect_board
from darts.sim import ThrowSim, build_model
from darts.twin import load_twin


@pytest.fixture(scope="module")
def twin():
    return load_twin("twin.yaml")


def frame_with_board(twin, centre, normal_az=0.0):
    """A synthetic frame: dark scene, the board's bright disc drawn where the pinhole puts it."""
    r = twin.board.radius_m * DOUBLE_IN / DOUBLE_OUT * EDGE_GROWTH  # as the real blob reads
    a = np.linspace(0, 2 * np.pi, 360)
    n = np.array([-np.cos(normal_az), -np.sin(normal_az), 0.0])
    u = np.cross([0, 0, 1.0], n)
    v = np.cross(n, u)
    pts = [project(twin, centre + r * (np.cos(t) * u + np.sin(t) * v)) for t in a]
    img = np.full((int(twin.camera.height_px), int(twin.camera.width_px), 3), 20, np.uint8)
    cv2.fillPoly(img, [np.round(np.array(pts) - 0.5).astype(np.int32)], (250, 245, 220))
    return img


def test_a_drawn_board_is_found_to_within_two_centimetres(twin):
    for dx, dz in ((0, 0), (0.05, 0.08), (-0.04, -0.08)):
        truth = np.array([twin.board.distance_m + dx, 0.0, twin.board.centre_height_m + dz])
        got = detect_board(frame_with_board(twin, truth), twin)
        assert got is not None
        assert np.linalg.norm(got.centre_m - truth) < 0.02
        assert got.normal @ np.array([-1.0, 0, 0]) > 0.99


def test_nothing_in_view_or_a_board_cut_by_the_frame_returns_none(twin):
    blank = np.full((480, 640, 3), 20, np.uint8)
    assert detect_board(blank, twin) is None
    truth = np.array([twin.board.distance_m, 0.0, twin.board.centre_height_m])
    img = frame_with_board(twin, truth)
    img[:, 330:] = 20  # the right part of the board is gone
    img[:, :5] = 255  # a blob touching the frame edge is not trusted either
    assert detect_board(img, twin) is None


def test_a_board_hidden_behind_the_arm_is_not_reported(twin):
    truth = np.array([twin.board.distance_m, 0.0, twin.board.centre_height_m])
    img = frame_with_board(twin, truth)
    cv2.rectangle(img, (0, 0), (639, 479), (20, 20, 20), 3)  # a dark frame leaves it detectable
    assert detect_board(img, twin) is not None
    img[150:330, 300:500] = (
        20  # an arm in front hides half the disc: the ellipse is no longer round
    )
    assert detect_board(img, twin) is None


@pytest.mark.skipif(not os.environ.get("MUJOCO_GL"), reason="set MUJOCO_GL=osmesa")
def test_the_rendered_board_is_found_within_two_centimetres(twin):
    sim = ThrowSim(twin, build_model(twin, visual=True))
    mujoco.mj_forward(sim.model, sim.data)
    try:
        r = mujoco.Renderer(sim.model, int(twin.camera.height_px), int(twin.camera.width_px))
    except Exception as e:  # no GL backend here
        pytest.skip(f"no GL backend: {e}")
    r.update_scene(sim.data, camera="board_cam")
    got = detect_board(r.render(), twin)
    r.close()
    truth = np.array([twin.board.distance_m, 0.0, twin.board.centre_height_m])
    assert got is not None and np.linalg.norm(got.centre_m - truth) < 0.02
