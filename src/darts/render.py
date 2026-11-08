# pyright: reportAttributeAccessIssue=false
"""Headless replay rendering. Needs a GL backend: EGL on GPU pods, OSMesa (`MUJOCO_GL=osmesa`)."""

import os
from pathlib import Path

import cv2
import imageio.v3 as iio
import mujoco
import numpy as np

from darts.game import START_SCORE
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


def throw_frames(
    twin: Twin, params: ThrowParams, sim: ThrowSim | None = None
) -> tuple[list[np.ndarray], ThrowResult]:
    """Throw once on a model with a painted board; the frames of the replay.

    The main view is the room; when the dart nears the board it cuts to a close-up of the hit.
    The mast camera's own view sits in the top-right corner throughout."""
    os.environ.setdefault("MUJOCO_GL", "egl")
    sim = sim or ThrowSim(twin, build_model(twin, visual=True))
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
    return frames, result


def write_video(frames: list[np.ndarray], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    iio.imwrite(out, np.stack(frames), fps=PLAYBACK_FPS, codec="libx264")


def render_throw(twin: Twin, params: ThrowParams, out: Path) -> ThrowResult:
    """Throw once and write the replay to `out` (mp4)."""
    frames, result = throw_frames(twin, params)
    write_video(frames, out)
    return result


def _caption(img: np.ndarray, lines: list[str]) -> np.ndarray:
    img = img.copy()
    for i, text in enumerate(lines):
        y = 26 + 26 * i
        cv2.putText(img, text, (11, y + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
        cv2.putText(img, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
    return img


def render_game(twin: Twin, log: list[dict], out: Path, max_darts: int | None = None) -> int:
    """A replay of a game from `play`'s log with the running score on top. Each dart's flight
    shows the score before it; the result and the new score hold for a second afterwards.
    Returns the number of darts rendered."""
    sim = ThrowSim(twin, build_model(twin, visual=True))
    frames: list[np.ndarray] = []
    before = START_SCORE
    for row in log[:max_darts]:
        flight, _ = throw_frames(twin, row["params"], sim)
        head = f"Turn {row['turn']}   aiming {row['target']}"
        frames += [_caption(f, [head, f"Score {before}"]) for f in flight]
        hit = row["hit"]
        what = (
            "bust!"
            if row["outcome"] == "bust"
            else "checkout!"
            if row["outcome"] == "checkout"
            else ""
        )
        landed = f"{hit.ring} {hit.segment or ''}".strip() if row["stuck"] else "no stick"
        end = _caption(
            flight[-1], [head, f"{landed}: {hit.points}  {what}", f"Score {row['remaining']}"]
        )
        frames += [end] * PLAYBACK_FPS
        before = row["remaining"]
    write_video(frames, out)
    return len(log[:max_darts])
