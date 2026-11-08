# pyright: reportAttributeAccessIssue=false
"""From a camera frame to the policy's state, and how wrong that is (DART-24, ADR-0003)."""

import dataclasses

import cv2
import mujoco
import numpy as np

from darts.camera import pose
from darts.detect import detect_board
from darts.interface import BOARD_NORMAL, REST_JOINTS, State
from darts.sim import ThrowSim, build_model
from darts.twin import Twin


def state_from_frame(rgb: np.ndarray, twin: Twin, y: float = 0.0, z: float = 0.0) -> State | None:
    """The policy state for a target `y` to the side and `z` above the board centre (the game
    names the target; the camera finds the board). None when the board is not in view."""
    found = detect_board(rgb, twin)
    if found is None:
        return None
    base = found.centre_m - np.array([0.0, 0.0, twin.mount.height_m])  # the base is on the stand
    return State(base + np.array([0.0, y, z]), found.normal, np.array(REST_JOINTS))


def render_frame(truth: Twin, nominal: Twin) -> np.ndarray:
    """The mast camera's frame with the board where `truth` puts it, the camera where `nominal`
    puts it (the estimator is told the nominal setup, as it would be on hardware)."""
    sim = ThrowSim(truth, build_model(truth, visual=True))
    m, cam = sim.model, sim.model.camera("board_cam").id
    pos, axes = pose(nominal)
    m.cam_pos[cam] = pos
    mujoco.mju_mat2Quat(m.cam_quat[cam], axes.ravel())
    mujoco.mj_forward(m, sim.data)
    r = mujoco.Renderer(m, int(nominal.camera.height_px), int(nominal.camera.width_px))
    r.update_scene(sim.data, camera="board_cam")
    frame = r.render()
    r.close()
    return frame


def degrade(rgb: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Image trouble a real camera has: lighting gain and offset, blur, sensor noise."""
    img = rgb.astype(np.float32) * rng.uniform(0.7, 1.3) + rng.uniform(-15, 15)
    blur = rng.uniform(0.0, 1.5)
    if blur > 0.1:
        img = cv2.GaussianBlur(img, (0, 0), blur)
    img += rng.normal(0.0, rng.uniform(0.0, 4.0), img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def measure(twin: Twin, n: int = 100, seed: int = 0, noisy: bool = True) -> dict:
    """Detector error over `n` random board poses (distance -5 to +10 cm, height +-10 cm from the
    twin's), each frame optionally degraded. Errors are in the arm base frame."""
    rng = np.random.default_rng(seed)
    errs, tilts, failed = [], [], 0
    for _ in range(n):
        dx, dz = rng.uniform(-0.05, 0.1), rng.uniform(-0.1, 0.1)
        board = dataclasses.replace(
            twin.board,
            distance_m=twin.board.distance_m + dx,
            centre_height_m=twin.board.centre_height_m + dz,
        )
        truth = dataclasses.replace(twin, board=board)
        frame = render_frame(truth, twin)
        s = state_from_frame(degrade(frame, rng) if noisy else frame, twin)
        if s is None:
            failed += 1
            continue
        want = np.array([board.distance_m, 0.0, board.centre_height_m - twin.mount.height_m])
        errs.append(s.target_in_base - want)
        cos = np.clip(s.board_normal_in_base @ np.array(BOARD_NORMAL), -1.0, 1.0)
        tilts.append(np.arccos(cos))
    e, norm = np.array(errs), np.linalg.norm(errs, axis=1)
    plane = np.linalg.norm(e[:, 1:], axis=1)
    return {
        "n": n,
        "noisy": noisy,
        "failure_rate": failed / n,
        "target_std_m": e.std(axis=0).tolist(),  # x (towards the board), y, z
        "target_error_m": {"median": float(np.median(norm)), "p95": float(np.percentile(norm, 95))},
        "board_plane_error_m": {
            "median": float(np.median(plane)),
            "p95": float(np.percentile(plane, 95)),
        },
        "normal_error_rad": {
            "median": float(np.median(tilts)),
            "p95": float(np.percentile(tilts, 95)),
        },
    }
