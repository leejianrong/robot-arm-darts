# pyright: reportAttributeAccessIssue=false
"""Headless replay rendering. Needs a GL backend: EGL on GPU pods, OSMesa (`MUJOCO_GL=osmesa`)."""

import os
from pathlib import Path

import imageio.v3 as iio
import mujoco
import numpy as np

from darts.sim import ThrowParams, ThrowResult, ThrowSim, build_model
from darts.twin import Twin

CAPTURE_FPS = 120  # simulated frames per second recorded
PLAYBACK_FPS = 30  # so the clip plays at a quarter of real speed


def render_throw(twin: Twin, params: ThrowParams, out: Path) -> ThrowResult:
    """Throw once on a model with a painted board and write the replay to `out` (mp4)."""
    os.environ.setdefault("MUJOCO_GL", "egl")
    sim = ThrowSim(twin, build_model(twin, visual=True))
    renderer = mujoco.Renderer(sim.model, height=480, width=640)
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = (twin.board.distance_m * 0.5, 0.0, twin.board.centre_height_m - 0.4)
    cam.distance, cam.azimuth, cam.elevation = 3.1, 38.0, -12.0

    def frame() -> np.ndarray:
        renderer.update_scene(sim.data, camera=cam)
        return renderer.render().copy()

    frames: list[np.ndarray] = []
    result = sim.throw(params, frames=frames, render=frame, fps=CAPTURE_FPS)
    renderer.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    iio.imwrite(out, np.stack(frames), fps=PLAYBACK_FPS, codec="libx264")
    return result
