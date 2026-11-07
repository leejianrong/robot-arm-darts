"""The mast camera: where it is, what it sees, and where a world point lands in its image."""

import numpy as np

from darts.twin import Twin


def pose(twin: Twin) -> tuple[np.ndarray, np.ndarray]:
    """(position, axes) in the world. Axes columns are the camera's right, up and back
    directions, MuJoCo's convention: it looks along -back, towards the board centre."""
    c, b = twin.camera, twin.board
    pos = np.array([c.x_m, c.y_m, c.z_m])
    back = pos - np.array([b.distance_m, 0.0, b.centre_height_m])
    back /= np.linalg.norm(back)
    right = np.cross([0.0, 0.0, 1.0], back)
    right /= np.linalg.norm(right)
    return pos, np.column_stack([right, np.cross(back, right), back])


def intrinsics(twin: Twin) -> np.ndarray:
    """3x3 pinhole matrix; pixel coordinates run right and down from the image's top-left corner."""
    c = twin.camera
    f = (c.height_px / 2) / np.tan(np.radians(c.fovy_deg) / 2)
    return np.array([[f, 0, c.width_px / 2], [0, f, c.height_px / 2], [0, 0, 1.0]])


def project(twin: Twin, point: np.ndarray) -> tuple[float, float]:
    """Pixel (u, v) of a world point, continuous: pixel i spans [i, i + 1)."""
    pos, axes = pose(twin)
    right, up, back = axes.T @ (np.asarray(point, dtype=float) - pos)
    depth = -back
    f = intrinsics(twin)
    return float(f[0, 0] * right / depth + f[0, 2]), float(f[1, 2] - f[1, 1] * up / depth)
