"""Regulation dartboard scoring: a tip point on the board face to a score."""

import math
from dataclasses import dataclass

import numpy as np

# Clockwise from the top, as the thrower sees the board.
SEGMENTS = (20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5)
# Ring edges in metres from the centre (regulation).
BULL, OUTER_BULL = 0.00635, 0.0159
TREBLE_IN, TREBLE_OUT = 0.099, 0.107
DOUBLE_IN, DOUBLE_OUT = 0.162, 0.170


@dataclass(frozen=True)
class Hit:
    points: int
    ring: str  # bull, outer_bull, single, double, treble or miss
    segment: int | None = None


def score_tip(y: float, z: float) -> Hit:
    """Score a tip at lateral offset `y` (towards the thrower's left) and height `z` above the
    board centre, both in metres."""
    r = math.hypot(y, z)
    if r <= BULL:
        return Hit(50, "bull")
    if r <= OUTER_BULL:
        return Hit(25, "outer_bull")
    if r > DOUBLE_OUT:
        return Hit(0, "miss")
    angle = math.degrees(math.atan2(-y, z)) % 360  # clockwise from the top
    seg = SEGMENTS[int(((angle + 9) % 360) // 18)]
    if TREBLE_IN <= r <= TREBLE_OUT:
        return Hit(3 * seg, "treble", seg)
    if r >= DOUBLE_IN:
        return Hit(2 * seg, "double", seg)
    return Hit(seg, "single", seg)


def board_texture(size: int = 512) -> np.ndarray:
    """RGB image of the board face as the thrower sees it, one pixel per 2*DOUBLE_OUT/size metres.

    Row 0 is the top. Segment numbers are not drawn.
    """
    c = (np.arange(size) + 0.5) / size * 2 * DOUBLE_OUT - DOUBLE_OUT
    right, up = np.meshgrid(c, -c)  # image x grows rightwards, image row grows downwards
    r = np.hypot(right, up)
    seg = ((np.degrees(np.arctan2(right, up)) + 9) % 360 // 18).astype(int)
    odd = seg % 2 == 1
    black, cream, red, green = (20, 20, 20), (235, 220, 180), (200, 30, 30), (20, 130, 60)
    img = np.empty((size, size, 3), np.uint8)
    img[:] = np.where(odd[..., None], cream, black)  # the singles
    ring = ((r >= TREBLE_IN) & (r <= TREBLE_OUT)) | ((r >= DOUBLE_IN) & (r <= DOUBLE_OUT))
    img[ring] = np.where(odd[ring][:, None], green, red)
    img[r <= OUTER_BULL] = red
    img[r <= BULL] = green
    img[r > DOUBLE_OUT] = black
    return img
