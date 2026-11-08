import cv2
import numpy as np
import pytest

from darts.board import DOUBLE_IN, DOUBLE_OUT
from darts.camera import project
from darts.estimate import state_from_frame
from darts.interface import target_state
from darts.twin import load_twin


@pytest.fixture(scope="module")
def twin():
    return load_twin("twin.yaml")


def drawn_board(twin):
    r = twin.board.radius_m * DOUBLE_IN / DOUBLE_OUT
    centre = np.array([twin.board.distance_m, 0.0, twin.board.centre_height_m])
    pts = [
        project(twin, centre + r * np.array([0.0, np.cos(t), np.sin(t)]))
        for t in np.linspace(0, 2 * np.pi, 360)
    ]
    img = np.full((480, 640, 3), 20, np.uint8)
    cv2.fillPoly(img, [np.round(np.array(pts) - 0.5).astype(np.int32)], (250, 245, 220))
    return img


def test_a_frame_round_trips_to_the_state_the_game_would_have_given(twin):
    """Pixels to base frame: the estimated state matches `target_state` for the same target."""
    got = state_from_frame(drawn_board(twin), twin, y=0.05, z=-0.08)
    want = target_state(twin, 0.05, -0.08)
    assert got is not None
    assert got.target_in_base == pytest.approx(want.target_in_base, abs=0.01)
    assert got.board_normal_in_base == pytest.approx(want.board_normal_in_base, abs=0.02)


def test_no_board_in_the_frame_gives_no_state(twin):
    assert state_from_frame(np.full((480, 640, 3), 20, np.uint8), twin) is None
