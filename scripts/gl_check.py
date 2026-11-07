"""Does this host render the mast camera the way the laptop does? One JSON line on stdout.

Run it under MUJOCO_GL=egl or osmesa and compare lines between hosts: image size, intrinsics, where
a marker lands (against the pinhole maths) and the board's pixel count must agree.
"""

import dataclasses
import json
import os

import mujoco
import numpy as np

from darts.camera import intrinsics, project
from darts.env import DartThrowEnv
from darts.interface import decode_action
from darts.policies import hand_tuned_policy
from darts.sim import ThrowSim
from darts.twin import load_twin
from darts.visibility import board_visibility

twin = load_twin("twin.yaml")
marker = dataclasses.replace(twin.dart, length_m=0.02, radius_m=0.03)
sim = ThrowSim(dataclasses.replace(twin, dart=marker))
point = np.array([0.35, 0.05, 1.75])
sim.data.qpos[sim._dart_qadr : sim._dart_qadr + 3] = point
mujoco.mj_forward(sim.model, sim.data)
h, w = int(twin.camera.height_px), int(twin.camera.width_px)
r = mujoco.Renderer(sim.model, h, w)
r.update_scene(sim.data, camera="board_cam")
rgb = r.render()
r.enable_segmentation_rendering()
r.update_scene(sim.data, camera="board_cam")
seg = r.render()
rows, cols = np.nonzero(seg[..., 0] == sim.model.geom("dart_barrel").id)
env = DartThrowEnv(twin)
env.reset(seed=10_000)
params, _ = decode_action(hand_tuned_policy(env.state(), np.random.default_rng(0)))
vis = board_visibility(twin, params)
u, v = project(twin, point)
print(
    json.dumps(
        {
            "gl": os.environ.get("MUJOCO_GL"),
            "image_hw": list(rgb.shape[:2]),
            "focal_px": round(float(intrinsics(twin)[0, 0]), 3),
            "marker_px": int(rows.size),
            "marker_centre_px": [round(cols.mean() + 0.5, 2), round(rows.mean() + 0.5, 2)],
            "marker_projected_px": [round(u, 2), round(v, 2)],
            "board_baseline_px": vis["baseline_px"],
            "board_min_visible": round(vis["min"], 4),
        }
    )
)
