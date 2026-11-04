import math

import pytest

from darts.board import DOUBLE_OUT, SEGMENTS, score_tip
from darts.twin import load_twin


def at(r_mm: float, clockwise_deg: float):
    """Board point from radius and angle clockwise from the top, as (y, z) in metres."""
    a = math.radians(clockwise_deg)
    return -r_mm / 1000 * math.sin(a), r_mm / 1000 * math.cos(a)


# (radius mm, clockwise degrees from top, expected points); numbers read off a real board.
CASES = [
    (0, 0, 50), (5, 90, 50), (10, 0, 25), (15, 200, 25),
    (60, 0, 20), (103, 0, 60), (166, 0, 40), (135, 0, 20),
    (60, 90, 6), (103, 90, 18), (166, 90, 12),
    (60, 180, 3), (103, 180, 9), (166, 180, 6),
    (60, 270, 11), (103, 270, 33), (166, 270, 22),
    (60, 18, 1), (103, 18, 3), (166, 18, 2),
    (60, 342, 5), (103, 342, 15), (166, 342, 10),
    (60, 8, 20), (60, 10, 1),  # either side of the 20/1 wire
    (60, 350, 5), (60, 352, 20),  # the 5/20 wire sits at 351 degrees
    (60, 332, 12),
    (98, 0, 20), (108, 0, 20), (171, 0, 0),
]  # fmt: skip


@pytest.mark.parametrize(("r", "deg", "points"), CASES)
def test_known_coordinates(r, deg, points):
    assert score_tip(*at(r, deg)).points == points


def test_segment_order_has_every_number_once():
    assert sorted(SEGMENTS) == list(range(1, 21))


def test_scoring_radius_matches_the_twin():
    assert load_twin().board.radius_m == pytest.approx(DOUBLE_OUT)
