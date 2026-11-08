"""One interface for the simulated and the real arm (ADR-0006, DART-29).

A throw is a short script of commands (`plan`). `run` plays it on any `Arm` and writes a log in one
format, so a sim run and a hardware run can be compared line by line (the sysid fitter reads it)."""

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import mujoco

from darts.sim import ARM_JOINTS, THROW_JOINTS, ThrowParams, ThrowSim

MAX_TARGET_RAD = math.pi
STATE_HZ = 50  # how often `run` samples the arm into the log
SETTLE_AFTER_RELEASE_S = 0.3


def check_targets(targets: dict[str, float]) -> dict[str, float]:
    """Reject anything an arm should never be asked: unknown joints, NaN, or a huge angle."""
    for joint, v in targets.items():
        if joint not in ARM_JOINTS:
            raise ValueError(f"unknown joint {joint!r}; the arm has {ARM_JOINTS}")
        if not math.isfinite(v) or abs(v) > MAX_TARGET_RAD:
            raise ValueError(f"{joint}: target {v!r} is not a finite angle within +-pi")
    return targets


@dataclass(frozen=True)
class ArmState:
    t: float  # seconds since `prepare`
    joint_pos: tuple[float, ...]  # ARM_JOINTS then the gripper, radians
    gripper_open: bool


class Arm(Protocol):
    def prepare(self, start: dict[str, float]) -> None:
        """Bring the arm to a start pose, holding the dart, and zero the clock."""

    def set_targets(self, targets: dict[str, float]) -> None:
        """Command joint position targets, radians; the arm moves at its own limits."""

    def open_gripper(self) -> None: ...

    def read_state(self) -> ArmState: ...

    def wait(self, seconds: float) -> None:
        """Let time pass (the sim steps; hardware sleeps)."""


@dataclass(frozen=True)
class Command:
    t: float
    kind: str  # prepare, set_targets or open_gripper
    values: dict[str, float]


def plan(p: ThrowParams) -> list[Command]:
    """The commands a throw means: start pose, swing to the end pose, open the jaw."""
    start = {n: v for n, v in zip(THROW_JOINTS, p.q_start, strict=True)} | {
        "shoulder_pan": p.pan_rad
    }
    end = {n: v for n, v in zip(THROW_JOINTS, p.q_end, strict=True)}
    return [
        Command(0.0, "prepare", start),
        Command(0.0, "set_targets", end),
        Command(p.t_release_s, "open_gripper", {}),
    ]


def run(arm: Arm, commands: Sequence[Command]) -> list[dict]:
    """Play the commands on the arm in time order; return the log (commands and sampled states)."""
    log: list[dict] = []
    dt = 1.0 / STATE_HZ
    now = 0.0
    end = commands[-1].t + SETTLE_AFTER_RELEASE_S

    def sample() -> None:
        s = arm.read_state()
        pos = [round(x, 6) for x in s.joint_pos]
        log.append(
            {"kind": "state", "t": round(s.t, 6), "joint_pos": pos, "gripper_open": s.gripper_open}
        )

    for c in sorted(commands, key=lambda c: c.t):
        while now + dt <= c.t:
            arm.wait(dt)
            now += dt
            sample()
        if c.kind == "prepare":
            arm.prepare(c.values)
        elif c.kind == "set_targets":
            arm.set_targets(c.values)
        elif c.kind == "open_gripper":
            arm.open_gripper()
        else:
            raise ValueError(f"unknown command {c.kind!r}")
        log.append({"kind": "command", "t": round(c.t, 6), "name": c.kind,
                    "values": {k: round(v, 6) for k, v in c.values.items()}})  # fmt: skip
        sample()
    while now + dt <= end:
        arm.wait(dt)
        now += dt
        sample()
    return log


def write_log(log: list[dict], path: Path) -> None:
    path.write_text("".join(json.dumps(line) + "\n" for line in log))


def read_log(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


class SimArm:
    """The MuJoCo arm behind `Arm`, driven through the servo model a scripted throw uses."""

    def __init__(self, sim: ThrowSim):
        self.sim = sim
        self._targets: dict[str, float] = {}
        self._open = False
        self._t0 = 0.0
        self._pending: list[tuple[float, str, dict[str, float]]] = []  # (acts at, kind, values)

    def prepare(self, start: dict[str, float]) -> None:
        check_targets(start)
        q = tuple(start.get(n, 0.0) for n in THROW_JOINTS)
        self.sim.reset(q, start.get("shoulder_pan", 0.0))  # type: ignore[arg-type]
        self._targets, self._open, self._pending = {}, False, []
        self._t0 = self.sim.data.time

    def set_targets(self, targets: dict[str, float]) -> None:
        lag = self.sim.twin.servo.latency_s
        self._pending.append((self.sim.data.time + lag, "targets", check_targets(dict(targets))))

    def open_gripper(self) -> None:
        tw = self.sim.twin
        at = self.sim.data.time + tw.servo.latency_s + tw.release.jaw_delay_s
        self._pending.append((at, "open", {}))

    def wait(self, seconds: float) -> None:
        s = self.sim
        for _ in range(round(seconds / s.model.opt.timestep)):
            for due in [c for c in self._pending if c[0] <= s.data.time + 1e-9]:
                self._pending.remove(due)
                if due[1] == "open":
                    self._open = True
                else:
                    self._targets |= due[2]
            s._derate_torque()
            for n, v in self._targets.items():
                s._slew(n, v)
            if self._open:
                s._slew("gripper", s.twin.release.jaw_open_rad)
            mujoco.mj_step(s.model, s.data)  # pyright: ignore[reportAttributeAccessIssue]

    def read_state(self) -> ArmState:
        s = self.sim
        q = [float(s.data.qpos[s._qadr(n)]) for n in (*ARM_JOINTS, "gripper")]
        return ArmState(s.data.time - self._t0, tuple(q), self._open)


class LeRobotArm:
    """The real arm through LeRobot, as a stub: it talks to any `backend` that has LeRobot's
    `send_action(dict)` and `get_observation() -> dict` (joint names ending `.pos`, in degrees).
    Nothing here has touched hardware; a fake backend stands in for it in tests."""

    def __init__(self, backend, gripper_open_rad: float):
        self.backend = backend
        self.gripper_open_rad = gripper_open_rad
        self._open = False
        self._t = 0.0

    def prepare(self, start: dict[str, float]) -> None:
        self.set_targets(check_targets(dict(start)))
        self._open, self._t = False, 0.0

    def set_targets(self, targets: dict[str, float]) -> None:
        check_targets(dict(targets))
        self.backend.send_action({f"{n}.pos": math.degrees(v) for n, v in targets.items()})

    def open_gripper(self) -> None:
        self.backend.send_action({"gripper.pos": math.degrees(self.gripper_open_rad)})
        self._open = True

    def wait(self, seconds: float) -> None:
        self.backend.wait(seconds)
        self._t += seconds

    def read_state(self) -> ArmState:
        obs = self.backend.get_observation()
        q = tuple(math.radians(obs[f"{n}.pos"]) for n in (*ARM_JOINTS, "gripper"))
        return ArmState(self._t, q, self._open)
