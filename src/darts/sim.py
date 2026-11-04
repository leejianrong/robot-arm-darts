# pyright: reportAttributeAccessIssue=false
"""SO-101 on a stand, a dart held by jaw friction, and a scripted planar throw (V1)."""

from dataclasses import dataclass, replace
from pathlib import Path

import mujoco
import numpy as np

from darts.aero import aero_wrench
from darts.board import board_texture, score_tip
from darts.twin import Twin

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / "assets" / "menagerie" / "robotstudio_so101" / "scene.xml"
ARM_JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll")
THROW_JOINTS = ("shoulder_lift", "elbow_flex", "wrist_flex")
# Dart pose in the gripper frame: pinched at the fingertips against the fixed jaw plate, barrel
# along the finger direction (-z), tip protruding forward. Placement found by experiment.
GRIP_X_OFFSET = -0.0098  # fixed jaw plate surface; dart centre is radius further along +x
GRIP_Z_CENTRE = -0.113
HOLD_AFTER_HIT_S = 1.0  # extra simulated time recorded after the dart meets the board
NO_POINT = (float("inf"), float("inf"))
RELEASE_CONFIRM_STEPS = 5  # consecutive steps without pad contact that count as released
CONTACT_IMPRATIO = 100.0
CONTACT_SOLREF = (0.004, 1.0)
JAW_CLAMP_START = -0.12  # jaw angle at reset, just short of contact
_GRIPPER_BODIES = ("gripper", "moving_jaw_so101_v1", "camera_mount")  # the hand: both jaws


def assets_available() -> bool:
    return SCENE.exists()


def _hand_collision_geoms(model: mujoco.MjModel) -> set[int]:
    bodies = {model.body(n).id for n in _GRIPPER_BODIES}
    return {
        i
        for i in range(model.ngeom)
        if int(model.geom_bodyid[i]) in bodies
        and (model.geom_contype[i] or model.geom_conaffinity[i])
    }


def build_model(twin: Twin, visual: bool = False) -> mujoco.MjModel:
    """Menagerie SO-101 on a stand, with a board marker, a free dart, and twin.yaml overrides."""
    spec = mujoco.MjSpec.from_file(str(SCENE))
    h = twin.mount.height_m
    spec.body("base").pos = [0, 0, h]
    spec.worldbody.add_geom(
        name="stand",
        type=mujoco.mjtGeom.mjGEOM_BOX,
        pos=[0, 0, (h - 0.003) / 2],
        size=[0.05, 0.05, (h - 0.003) / 2],
        rgba=[0.4, 0.4, 0.45, 1],
    )
    spec.worldbody.add_geom(  # board face: darts that fail the stick test bounce off it
        name="board_face",
        type=mujoco.mjtGeom.mjGEOM_CYLINDER,
        pos=[twin.board.distance_m + 0.01, 0, twin.board.centre_height_m],
        quat=[0.70710678, 0, 0.70710678, 0],
        size=[twin.board.radius_m, 0.01, 0],
        rgba=[0.1, 0.1, 0.1, 1],
    )
    if visual:  # a painted square in front of the face, for replays only
        img = board_texture()
        spec.add_texture(
            name="board", type=mujoco.mjtTexture.mjTEXTURE_2D, width=img.shape[1],
            height=img.shape[0], nchannel=3, data=img.ravel().tolist(),
        )  # fmt: skip
        spec.add_material(name="board", textures=["", "board"])
        spec.worldbody.add_geom(
            name="board_paint", type=mujoco.mjtGeom.mjGEOM_BOX, material="board",
            pos=[twin.board.distance_m - 0.0005, 0, twin.board.centre_height_m],
            size=[0.0005, twin.board.radius_m, twin.board.radius_m], contype=0, conaffinity=0,
        )  # fmt: skip
    dart = spec.worldbody.add_body(name="dart")
    dart.add_freejoint()
    half = twin.dart.length_m / 2
    dart.add_geom(
        name="dart_barrel",
        type=mujoco.mjtGeom.mjGEOM_CAPSULE,
        fromto=[0, 0, -half, 0, 0, half],
        size=[twin.dart.radius_m, 0, 0],
        mass=twin.dart.mass_kg,
        friction=[twin.release.pad_friction, 0.005, 0.0001],
        rgba=[0.9, 0.1, 0.1, 1],
    )
    model = spec.compile()
    model.opt.timestep = twin.sim.timestep_s
    model.opt.gravity[:] = (0, 0, -twin.sim.gravity_m_s2)
    model.actuator_gainprm[:, 0] = twin.servo.kp
    model.actuator_biasprm[:, 1] = -twin.servo.kp
    model.actuator_biasprm[:, 2] = -twin.servo.kv
    model.actuator_forcerange[:] = (-twin.servo.torque_limit_nm, twin.servo.torque_limit_nm)
    # Contact numerics, tuned so a pinched dart neither creeps at rest (0.15 mm/s) nor slips in a
    # hard swing; the Menagerie defaults let it creep out in 0.5 s. They are solver settings, not
    # physical parameters, so they stay out of twin.yaml.
    model.opt.impratio = CONTACT_IMPRATIO
    for i in _hand_collision_geoms(model):
        model.geom_solref[i] = CONTACT_SOLREF
        model.geom_friction[i, 0] = twin.release.pad_friction  # pad friction comes from the twin
    model.geom_solref[model.geom("dart_barrel").id] = CONTACT_SOLREF
    return model


@dataclass(frozen=True)
class ThrowParams:
    q_start: tuple[float, float, float]  # shoulder_lift, elbow_flex, wrist_flex
    q_end: tuple[float, float, float]
    t_release_s: float  # time after motion start that the jaw is commanded open
    pan_rad: float = 0.0  # shoulder_pan, held for the whole throw; aims the throw sideways


@dataclass(frozen=True)
class ThrowResult:
    released: bool
    release_speed_m_s: float
    release_angle_rad: float  # above horizontal
    release_height_m: float
    crossed_plane: bool  # reached the board plane before hitting the floor or timing out
    board_yz: tuple[float, float]  # contact or crossing point relative to the centre (inf if none)
    shortfall_m: float  # how far short of the board plane it ended (0 if it crossed)
    hit_board: bool  # crossed inside the scoring radius
    slipped_early: bool = False  # dart left the jaws before the release command
    diverged: bool = False  # the solver blew up (non-finite state); the throw is invalid
    collided: bool = False  # the dart touched the arm or stand outside the jaw pads
    stuck: bool = False  # the tip hit the board fast and square enough to stick
    score: int = 0  # points for a stuck dart

    @property
    def miss_m(self) -> float:
        return float(np.hypot(*self.board_yz))


class ThrowSim:
    def __init__(self, twin: Twin, model: mujoco.MjModel | None = None):
        self.twin = twin
        self.model = model or build_model(twin)
        self.data = mujoco.MjData(self.model)
        m = self.model
        self._jid = {n: m.joint(n).id for n in (*ARM_JOINTS, "gripper")}
        self._aid = {n: m.actuator(n).id for n in (*ARM_JOINTS, "gripper")}
        self._gripper_body = m.body("gripper").id
        self._dart_geom = m.geom("dart_barrel").id
        self._floor_geom = m.geom("floor").id
        self._board_geom = m.geom("board_face").id
        self._dart_body = m.body("dart").id
        self._dart_qadr = int(m.jnt_qposadr[m.body_jntadr[self._dart_body]])
        self._dart_vadr = int(m.jnt_dofadr[m.body_jntadr[self._dart_body]])
        self._gripper_geoms = _hand_collision_geoms(m)

    def _qadr(self, joint: str) -> int:
        return int(self.model.jnt_qposadr[self._jid[joint]])

    def _place_dart_in_grip(self) -> None:
        m, d = self.model, self.data
        mujoco.mj_forward(m, d)
        rot = d.xmat[self._gripper_body].reshape(3, 3)
        local = np.array([GRIP_X_OFFSET + self.twin.dart.radius_m, 0.0, GRIP_Z_CENTRE])
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, rot.flatten())
        a = self._dart_qadr
        d.qpos[a : a + 3] = d.xpos[self._gripper_body] + rot @ local
        d.qpos[a + 3 : a + 7] = quat

    def reset(
        self, q_start: tuple[float, float, float], pan_rad: float = 0.0, settle_s: float = 0.4
    ) -> None:
        mujoco.mj_resetData(self.model, self.data)
        d = self.data
        for n, v in zip(THROW_JOINTS, q_start, strict=True):
            d.qpos[self._qadr(n)] = v
            d.ctrl[self._aid[n]] = v
        d.qpos[self._qadr("shoulder_pan")] = pan_rad
        d.ctrl[self._aid["shoulder_pan"]] = pan_rad
        d.qpos[self._qadr("gripper")] = JAW_CLAMP_START
        d.ctrl[self._aid["gripper"]] = JAW_CLAMP_START
        self._place_dart_in_grip()
        for _ in range(round(settle_s / self.model.opt.timestep)):
            self._slew("gripper", self.twin.release.jaw_hold_rad)
            mujoco.mj_step(self.model, d)

    def dart_contacts(self) -> tuple[bool, bool, bool]:
        """(touching a jaw pad, touching the arm or stand, touching the floor); never the board."""
        pad = other = floor = False
        d = self.data
        for i in range(d.ncon):
            c = d.contact[i]
            pair = {int(c.geom1), int(c.geom2)}
            if self._dart_geom not in pair:
                continue
            if pair & self._gripper_geoms:
                pad = True
            elif self._floor_geom in pair:
                floor = True
            elif self._board_geom not in pair:
                other = True
        return pad, other, floor

    def _board_contact(self, pre_vel: np.ndarray) -> tuple[bool, float, float] | None:
        """If the dart touches the board: (sticks, y, z) of the contact relative to the centre.

        `pre_vel` is the velocity before the step; the contacts belong to that state.
        """
        d, b = self.data, self.twin.board
        for i in range(d.ncon):
            c = d.contact[i]
            if {int(c.geom1), int(c.geom2)} == {self._dart_geom, self._board_geom}:
                axis_x = d.xmat[self._dart_body].reshape(3, 3)[0, 2]  # tip direction vs normal
                stick = (
                    pre_vel[0] >= b.stick_min_speed_m_s
                    and np.arccos(np.clip(axis_x, -1, 1)) <= b.stick_max_angle_rad
                )
                return bool(stick), float(c.pos[1]), float(c.pos[2] - b.centre_height_m)
        return None

    def _apply_aero(self) -> None:
        d, a = self.data, self._dart_vadr
        rot = d.xmat[self._dart_body].reshape(3, 3)
        force, torque = aero_wrench(
            d.qvel[a : a + 3], rot @ d.qvel[a + 3 : a + 6], rot[:, 2], self.twin.aero
        )
        d.xfrc_applied[self._dart_body] = (*force, *torque)

    def launch(
        self, pos: tuple[float, float, float], vel: tuple[float, float, float], max_time_s=2.0
    ) -> ThrowResult:
        """Free flight of the dart from `pos` with velocity `vel`, tip first, no arm involved."""
        m, d = self.model, self.data
        mujoco.mj_resetData(m, d)
        v = np.asarray(vel, dtype=float)
        z = v / np.linalg.norm(v)
        x = np.cross([0.0, 1.0, 0.0], z)
        x /= np.linalg.norm(x)
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, np.column_stack([x, np.cross(z, x), z]).flatten())
        a, b = self._dart_qadr, self._dart_vadr
        d.qpos[a : a + 3], d.qpos[a + 3 : a + 7], d.qvel[b : b + 3] = pos, quat, v
        speed = float(np.linalg.norm(v))
        angle = float(np.arctan2(v[2], np.hypot(v[0], v[1])))
        base = ThrowResult(True, speed, angle, pos[2], False, NO_POINT, 0.0, False)
        for _ in range(round(max_time_s / m.opt.timestep)):
            pre_vel = d.qvel[b : b + 3].copy()
            self._apply_aero()
            mujoco.mj_step(m, d)
            if (c := self._board_contact(pre_vel)) is not None:
                stuck, y, zc = c
                return replace(
                    base, crossed_plane=True, board_yz=(y, zc), hit_board=True, stuck=stuck,
                    score=score_tip(y, zc).points if stuck else 0,
                )  # fmt: skip
            at = self.dart_state()[0]
            if at[0] >= self.twin.board.distance_m:  # flew past the board face, high or wide
                yz = (float(at[1]), float(at[2] - self.twin.board.centre_height_m))
                return replace(base, crossed_plane=True, board_yz=yz)
            if self.dart_contacts()[2] or at[2] <= 0.0:
                break
        short = max(0.0, self.twin.board.distance_m - self.dart_state()[0][0])
        return replace(base, shortfall_m=short)

    def _slew(self, name: str, target: float) -> None:
        """Rate-limit the position command to the servo velocity limit."""
        a = self._aid[name]
        step = self.twin.servo.velocity_limit_rad_s * self.model.opt.timestep
        cur = self.data.ctrl[a]
        self.data.ctrl[a] = cur + float(np.clip(target - cur, -step, step))

    def dart_state(self) -> tuple[np.ndarray, np.ndarray]:
        a, v = self._dart_qadr, self._dart_vadr
        return self.data.qpos[a : a + 3].copy(), self.data.qvel[v : v + 3].copy()

    def _command(self, p: ThrowParams, t: float) -> None:
        for n, target in zip(THROW_JOINTS, p.q_end, strict=True):
            self._slew(n, target)
        if t >= p.t_release_s:
            self._slew("gripper", self.twin.release.jaw_open_rad)

    def throw(
        self,
        p: ThrowParams,
        max_time_s: float = 3.0,
        frames: list | None = None,
        render=None,
        fps: int = 30,
    ) -> ThrowResult:
        """Run one scripted throw. `render` is a callable returning an RGB frame, if given."""
        self.reset(p.q_start, p.pan_rad)
        m, d, tw = self.model, self.data, self.twin
        dt = m.opt.timestep
        board_x, zc = tw.board.distance_m, tw.board.centre_height_m
        released, speed, angle, height = False, 0.0, 0.0, 0.0
        crossed, yz, hit, slipped, diverged = False, NO_POINT, False, False, False
        collided, stuck, score = False, False, 0
        off_pad_steps, first_off = 0, None
        t, next_frame = 0.0, 0.0
        prev = self.dart_state()[0]

        def capture() -> None:
            nonlocal next_frame
            if render is not None and frames is not None and t >= next_frame:
                frames.append(render())
                next_frame += 1.0 / fps

        while t < p.t_release_s + max_time_s:
            self._command(p, t)
            pre_vel = self.dart_state()[1]
            if released:
                self._apply_aero()
            mujoco.mj_step(m, d)
            t += dt
            capture()
            pos, vel = self.dart_state()
            if not (np.isfinite(pos).all() and np.isfinite(d.qacc).all()):
                diverged = True
                break
            on_pad, other, on_floor = self.dart_contacts()
            if other:
                collided = True
                break
            if not released:
                if on_pad:  # contact can flicker while the jaw still pushes the dart
                    off_pad_steps, first_off = 0, None
                else:
                    off_pad_steps += 1
                    first_off = first_off or (t, pos, vel)
                if off_pad_steps >= RELEASE_CONFIRM_STEPS and first_off is not None:
                    released = True
                    t_off, p_off, v_off = first_off
                    slipped = t_off < p.t_release_s
                    speed = float(np.linalg.norm(v_off))
                    angle = float(np.arctan2(v_off[2], np.hypot(v_off[0], v_off[1])))
                    height = float(p_off[2])
            if released:
                if (c := self._board_contact(pre_vel)) is not None:
                    stuck, y, zb = c
                    yz, crossed, hit = (y, zb), True, True
                    score = score_tip(y, zb).points if stuck else 0
                    break
                if prev[0] < board_x <= pos[0]:
                    f = (board_x - prev[0]) / (pos[0] - prev[0])
                    cross = prev + f * (pos - prev)
                    yz = (float(cross[1]), float(cross[2] - zc))
                    crossed, hit = True, np.hypot(*yz) <= tw.board.radius_m
                    break
                if on_floor or pos[2] <= 0.0:
                    break
            prev = pos
        if hit:  # keep recording after contact: a stuck dart stays put, a bounce plays out
            a, v = self._dart_qadr, self._dart_vadr
            pose = d.qpos[a : a + 7].copy()
            for _ in range(round(HOLD_AFTER_HIT_S / dt)):
                self._command(p, t)
                if stuck:
                    d.qpos[a : a + 7], d.qvel[v : v + 6] = pose, 0.0
                else:
                    self._apply_aero()
                mujoco.mj_step(m, d)
                t += dt
                capture()
        shortfall = 0.0 if crossed else max(0.0, board_x - float(self.dart_state()[0][0]))
        return ThrowResult(
            released=released,
            release_speed_m_s=speed,
            release_angle_rad=angle,
            release_height_m=height,
            crossed_plane=crossed,
            board_yz=yz,
            shortfall_m=shortfall,
            hit_board=hit,
            slipped_early=slipped,
            diverged=diverged,
            collided=collided,
            stuck=stuck,
            score=score,
        )
