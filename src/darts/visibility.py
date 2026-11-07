# pyright: reportAttributeAccessIssue=false
"""Does the arm ever hide the board from the mast camera? A segmentation render per frame."""

import os

import mujoco
import numpy as np

from darts.sim import ThrowParams, ThrowSim, build_model
from darts.twin import Twin

FPS = 20  # simulated frames checked per second of throw
MIN_VISIBLE = 0.98  # the board stays at least this visible in every frame (see docs/camera-mast.md)


def board_visibility(twin: Twin, params: ThrowParams, sim: ThrowSim | None = None) -> dict:
    """Visible fraction of the board face in every frame of one throw, against the same view with
    the arm hidden. Returns {"min", "frames", "worst_frame", "baseline_px"}."""
    os.environ.setdefault("MUJOCO_GL", "egl")
    sim = sim or ThrowSim(twin, build_model(twin, visual=True))
    m = sim.model
    h, w = int(twin.camera.height_px), int(twin.camera.width_px)
    renderer = mujoco.Renderer(m, h, w)
    renderer.enable_segmentation_rendering()
    board = m.geom("board_paint").id

    def board_pixels(opt=None) -> int:
        renderer.update_scene(sim.data, camera="board_cam", scene_option=opt)
        return int((renderer.render()[..., 0] == board).sum())

    sim.reset(params.q_start, params.pan_rad)
    only_world = mujoco.MjvOption()
    only_world.geomgroup[:] = 0
    only_world.geomgroup[0] = 1  # group 0 holds the room and board; the arm lives in other groups
    baseline = board_pixels(only_world)
    fractions: list[float] = []

    def capture() -> np.ndarray:
        fractions.append(board_pixels() / baseline)
        return np.zeros((1, 1, 3))

    sim.throw(params, frames=[], render=capture, fps=FPS)
    renderer.close()
    worst = int(np.argmin(fractions))
    return {
        "min": float(fractions[worst]),
        "frames": len(fractions),
        "worst_frame": worst,
        "baseline_px": baseline,
    }
