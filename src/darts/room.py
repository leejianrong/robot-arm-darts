# pyright: reportAttributeAccessIssue=false
"""A pub corner around the throw, for replays only: no collisions, so scores are unchanged."""

import mujoco
import numpy as np

from darts.twin import Twin

WALL_X, SIDE_Y, BACK_X, CEILING_Z = 0.62, 2.6, -3.0, 3.0  # the room's walls, metres from the base


def _wood(size: int = 256, plank: int = 32, base=(150, 98, 55)) -> np.ndarray:
    rng = np.random.default_rng(1)
    rows = np.arange(size) // plank
    tone = rng.uniform(0.8, 1.15, rows.max() + 1)[rows][:, None]
    grain = 1 + 0.06 * np.sin(np.arange(size)[None, :] * 0.35 + rows[:, None] * 2.0)
    img = np.array(base)[None, None, :] * (tone * grain)[..., None]
    img[::plank, :] *= 0.45  # the gap between planks
    return np.clip(img, 0, 255).astype(np.uint8)


def _material(
    spec, name: str, rgb=None, img=None, rgba=None, repeat=(1, 1), emission=0.0, refl=0.0
):
    if img is not None:
        spec.add_texture(
            name=name, type=mujoco.mjtTexture.mjTEXTURE_2D, width=img.shape[1],
            height=img.shape[0], nchannel=3, data=img.ravel().tolist(),
        )  # fmt: skip
    m = spec.add_material(name=name, textures=["", name] if img is not None else [""])
    m.rgba = rgba or [*(np.array(rgb or (255, 255, 255)) / 255), 1]
    m.texrepeat, m.texuniform, m.emission, m.reflectance = list(repeat), True, emission, refl
    return name


def _box(spec, name, pos, size, material):
    spec.worldbody.add_geom(
        name=name, type=mujoco.mjtGeom.mjGEOM_BOX, pos=pos, size=size, material=material,
        contype=0, conaffinity=0,
    )  # fmt: skip


def add_room(spec, twin: Twin) -> None:
    b = twin.board
    floor = _material(spec, "room_floor", img=_wood(), repeat=(2, 2), refl=0.08)
    spec.geom("floor").material = floor
    wall = _material(spec, "room_wall", rgb=(88, 38, 42))
    panel = _material(spec, "room_panel", img=_wood(base=(78, 46, 28)), repeat=(1, 1))
    dark = _material(spec, "room_dark", rgb=(26, 22, 22))
    metal = _material(spec, "room_stand", rgb=(70, 74, 82), refl=0.1)
    glow = _material(spec, "room_glow", rgb=(255, 190, 110), emission=1.0)
    green = _material(spec, "room_green", rgb=(28, 70, 52))
    cx, hw = (WALL_X + BACK_X) / 2, (WALL_X - BACK_X) / 2
    _box(spec, "wall_front", [WALL_X + 0.02, 0, CEILING_Z / 2], [0.02, SIDE_Y, CEILING_Z / 2], wall)
    _box(spec, "wall_back", [BACK_X, 0, CEILING_Z / 2], [0.02, SIDE_Y, CEILING_Z / 2], wall)
    for s in (-1, 1):
        _box(
            spec, f"wall_side{s}", [cx, s * SIDE_Y, CEILING_Z / 2], [hw, 0.02, CEILING_Z / 2], wall
        )
    _box(spec, "ceiling", [cx, 0, CEILING_Z], [hw, SIDE_Y, 0.02], dark)
    for s in (-1, 1):  # wood wainscot along the walls
        _box(spec, f"wainscot{s}", [cx, s * (SIDE_Y - 0.03), 0.55], [hw, 0.03, 0.55], panel)
    _box(spec, "wainscot_front", [WALL_X - 0.03, 0, 0.55], [0.03, SIDE_Y, 0.55], panel)
    # the board: a cabinet with a dark surround and a glowing rail, centred on the board face
    cabinet = [b.distance_m + 0.03, 0, b.centre_height_m]
    _box(spec, "cabinet", cabinet, [0.03, 0.34, 0.34], panel)
    _box(spec, "surround", [b.distance_m + 0.005, 0, b.centre_height_m], [0.004, 0.27, 0.27], green)
    _box(
        spec,
        "rail",
        [b.distance_m + 0.005, 0, b.centre_height_m + 0.335],
        [0.01, 0.30, 0.012],
        glow,
    )
    _box(spec, "throw_line", [0.0, 0.0, 0.002], [0.03, 0.4, 0.002], glow)
    # a bar along the right-hand wall, with stools
    _box(spec, "bar", [cx, SIDE_Y - 0.45, 0.52], [1.2, 0.25, 0.52], panel)
    _box(spec, "bar_top", [cx, SIDE_Y - 0.45, 1.06], [1.3, 0.3, 0.025], dark)
    for i, x in enumerate((-1.6, -0.9, -0.2)):
        spec.worldbody.add_geom(
            name=f"stool{i}", type=mujoco.mjtGeom.mjGEOM_CYLINDER, pos=[x, SIDE_Y - 1.0, 0.36],
            size=[0.17, 0.02, 0], material=dark, contype=0, conaffinity=0,
        )  # fmt: skip
        _box(spec, f"stool_leg{i}", [x, SIDE_Y - 1.0, 0.17], [0.025, 0.025, 0.17], metal)
    _box(spec, "bar_shelf", [cx, SIDE_Y - 0.03, 1.5], [1.2, 0.03, 0.02], panel)
    for i, x in enumerate(np.linspace(-1.8, 0.2, 7)):  # bottles on the shelf
        spec.worldbody.add_geom(
            name=f"bottle{i}", type=mujoco.mjtGeom.mjGEOM_CYLINDER, pos=[x, SIDE_Y - 0.08, 1.63],
            size=[0.035, 0.11, 0], material=green if i % 2 else glow, contype=0, conaffinity=0,
        )  # fmt: skip
    # lights: a warm spot on the board and soft fill, with the shadows that come with them
    spec.worldbody.add_light(
        name="board_spot", type=mujoco.mjtLightType.mjLIGHT_SPOT, pos=[0.0, 0.0, 2.7],
        dir=[b.distance_m, 0.0, b.centre_height_m - 2.7], diffuse=[1.0, 0.85, 0.65],
        castshadow=True, cutoff=45,
    )  # fmt: skip
    spec.worldbody.add_light(name="fill", pos=[-1.0, 0.0, 2.8], dir=[0.2, 0, -1],
                             diffuse=[0.35, 0.3, 0.28], castshadow=False)  # fmt: skip
    spec.stat.extent = 4.0
