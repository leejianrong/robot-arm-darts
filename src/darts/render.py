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


CLOSE_UP_M = 0.35  # the view cuts to the board when the dart is this close to it
INSET = (150, 200)  # (height, width) of the mast camera's picture-in-picture


def _free_camera(lookat, distance: float, azimuth: float, elevation: float) -> mujoco.MjvCamera:
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = lookat
    cam.distance, cam.azimuth, cam.elevation = distance, azimuth, elevation
    return cam


def render_throw(twin: Twin, params: ThrowParams, out: Path) -> ThrowResult:
    """Throw once on a model with a painted board and write the replay to `out` (mp4).

    The main view is the room; when the dart nears the board it cuts to a close-up of the hit.
    The mast camera's own view sits in the top-right corner throughout."""
    os.environ.setdefault("MUJOCO_GL", "egl")
    sim = ThrowSim(twin, build_model(twin, visual=True))
    renderer = mujoco.Renderer(sim.model, height=480, width=640)
    inset = mujoco.Renderer(sim.model, height=INSET[0], width=INSET[1])
    b = twin.board
    room = _free_camera((b.distance_m * 0.5, 0.0, b.centre_height_m - 0.4), 3.1, 38.0, -12.0)
    close = _free_camera((b.distance_m, 0.0, b.centre_height_m), 0.9, 60.0, -4.0)

    def frame() -> np.ndarray:
        near = sim.dart_state()[0][0] > b.distance_m - CLOSE_UP_M
        renderer.update_scene(sim.data, camera=close if near else room)
        img = renderer.render().copy()
        inset.update_scene(sim.data, camera="board_cam")
        h, w = INSET
        img[8 : h + 8, -w - 8 : -8] = inset.render()
        img[h + 8 : h + 10, -w - 8 : -8] = 255  # a thin frame under the inset
        return img

    frames: list[np.ndarray] = []
    result = sim.throw(params, frames=frames, render=frame, fps=CAPTURE_FPS)
    renderer.close()
    inset.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    iio.imwrite(out, np.stack(frames), fps=PLAYBACK_FPS, codec="libx264")
    return result
