# pyright: reportAttributeAccessIssue=false
"""Headless replay rendering. Needs a GL backend (EGL on GPU pods, OSMesa otherwise)."""

import os
from pathlib import Path

import imageio.v3 as iio
import mujoco
import numpy as np

from darts.sim import ThrowParams, ThrowSim


def render_throw(sim: ThrowSim, params: ThrowParams, out: Path, fps: int = 30) -> None:
    os.environ.setdefault("MUJOCO_GL", "egl")
    renderer = mujoco.Renderer(sim.model, height=480, width=640)
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = (0.7, 0.0, 0.25)
    cam.distance, cam.azimuth, cam.elevation = 2.4, 90.0, -8.0

    def frame() -> np.ndarray:
        renderer.update_scene(sim.data, camera=cam)
        return renderer.render().copy()

    frames: list[np.ndarray] = []
    sim.throw(params, frames=frames, render=frame, fps=fps)
    renderer.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    iio.imwrite(out, np.stack(frames), fps=fps, codec="libx264")
