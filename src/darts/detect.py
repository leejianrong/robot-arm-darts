"""Find the board in a mast-camera image and recover where it is (DART-23, ADR-0003).

The cream wedges inside the dartboard's double ring are the brightest large round thing in view.
We threshold the bright pixels, fit an ellipse to the biggest round blob and solve for the circle
(centre and normal) whose projection matches it, starting from the ellipse itself. Returns None
when the board is not fully in view, never a guess."""

from dataclasses import dataclass

import cv2
import numpy as np
from scipy.optimize import least_squares

from darts.board import DOUBLE_IN, DOUBLE_OUT
from darts.camera import intrinsics, pose
from darts.twin import Twin

EDGE_GROWTH = (
    1.02  # the closed bright blob reads about 2% bigger than the ring; fitted on 100 renders
)
MIN_AREA_PX = 400
BORDER_PX = 2  # a blob touching the image edge may be cut off, so its outline is not the board's
BRIGHT = 150  # HSV value of the lit ring and cream wedges; the wall and wood are darker
MAX_OUTLINE_ERR = 0.08  # mean ellipse-equation error of the outline; a cut disc or the rail fail


@dataclass(frozen=True)
class BoardPose:
    centre_m: np.ndarray  # board centre in the world frame
    normal: np.ndarray  # unit normal of the face, pointing at the thrower, world frame


def _ellipse(rgb: np.ndarray):
    """cv2 ellipse ((cx, cy), (w, h), angle) of the board's outer ring, or None."""
    hue, sat, val = cv2.split(cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV))
    arm = (
        (hue > 15) & (hue < 40) & (sat > 120)
    )  # the yellow arm is bright too and touches the board
    mask = cv2.morphologyEx(
        ((val > BRIGHT) & ~arm).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8)
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    best = None
    for c in contours:
        area = cv2.contourArea(c)
        if area < MIN_AREA_PX or len(c) < 5:
            continue
        x, y, w, h = cv2.boundingRect(c)
        if x < BORDER_PX or y < BORDER_PX:
            continue
        if x + w > rgb.shape[1] - BORDER_PX or y + h > rgb.shape[0] - BORDER_PX:
            continue
        fitted = cv2.fitEllipse(c)
        if np.abs(_implicit(fitted, c.reshape(-1, 2).astype(float))).mean() > MAX_OUTLINE_ERR:
            continue
        (cx, cy), axes_px, deg = fitted
        e = (
            (cx + 0.5, cy + 0.5),
            axes_px,
            deg,
        )  # contour pixels are indices; pixel i spans [i, i+1)
        if best is None or area > best[0]:
            best = (area, e)
    return None if best is None else best[1]


def _implicit(e, pts: np.ndarray) -> np.ndarray:
    """Zero on the ellipse, positive outside: the ellipse equation at image points."""
    (cx, cy), (w, h), deg = e
    t = np.radians(deg)
    d = pts - [cx, cy]
    u = d[:, 0] * np.cos(t) + d[:, 1] * np.sin(t)
    v = -d[:, 0] * np.sin(t) + d[:, 1] * np.cos(t)
    return (2 * u / w) ** 2 + (2 * v / h) ** 2 - 1


def detect_board(rgb: np.ndarray, twin: Twin) -> BoardPose | None:
    """Pose of the board from one RGB frame of the mast camera, or None if it is not in view."""
    e = _ellipse(rgb)
    if e is None:
        return None
    pos, axes = pose(twin)
    to_world = axes * np.array([1.0, -1.0, -1.0])  # OpenCV camera axes (right, down, forward)
    k = intrinsics(twin)
    r = EDGE_GROWTH * twin.board.radius_m * DOUBLE_IN / DOUBLE_OUT  # wedges end at the double ring
    ang = np.linspace(0, 2 * np.pi, 48, endpoint=False)
    ring = np.stack([np.cos(ang), np.sin(ang)])  # unit circle in the board's plane

    def normal_of(az: float, el: float) -> np.ndarray:  # world normal from azimuth and elevation
        return np.array([-np.cos(el) * np.cos(az), -np.cos(el) * np.sin(az), np.sin(el)])

    def project_ring(x: np.ndarray) -> np.ndarray:
        n = normal_of(x[3], x[4])
        a = np.cross([0.0, 0.0, 1.0], n)
        a /= np.linalg.norm(a)
        b = np.cross(n, a)
        world = x[:3, None] + r * (a[:, None] * ring[0] + b[:, None] * ring[1])
        cam = to_world.T @ (world - pos[:, None])
        return (k[:2, :2] @ (cam[:2] / cam[2]) + k[:2, 2:]).T

    # start from the ellipse itself: its centre gives the ray, its long axis the range
    (cx, cy), (w, h), _ = e
    depth = k[0, 0] * 2 * r / max(w, h)
    ray = to_world @ np.array([(cx - k[0, 2]) / k[0, 0], (cy - k[1, 2]) / k[1, 1], 1.0])
    start = np.array([*(pos + depth * ray), 0.0, 0.0])
    fit = least_squares(lambda x: _implicit(e, project_ring(x)), start)
    if not fit.success:
        return None
    return BoardPose(fit.x[:3], normal_of(fit.x[3], fit.x[4]))
