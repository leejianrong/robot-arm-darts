"""Fit servo gain, latency and jaw delay to an arm log by replaying its commands (DART-30).

A log is what `darts.arm.run` writes: the commands sent and the joint positions read back, from the
sim or from LeRobot on the real arm. The fit replays the logged commands on a `SimArm`, with the
candidate numbers in the twin, and minimises the joint-position error against the logged states."""

import dataclasses
from collections.abc import Sequence

import numpy as np
from scipy.optimize import least_squares

from darts.arm import Command, SimArm, run
from darts.sim import ThrowSim
from darts.twin import Twin

MS = 1e-3
# Parameters: one gain ratio scaling kp and kv together (as `randomise` does: a log cannot tell
# them apart, the fit gave kp 15% off alone), then latency and jaw delay in milliseconds. A
# finite-difference step must exceed one sim step (2 ms) for the delays to register.
START = np.array([1.0, 10.0, 10.0])
LOWER = np.array([0.2, 0.0, 0.0])
UPPER = np.array([5.0, 150.0, 150.0])
FD_STEP = np.array([0.1, 0.3, 0.3])


def commands_of(log: list[dict]) -> list[Command]:
    return [Command(e["t"], e["name"], e["values"]) for e in log if e["kind"] == "command"]


def states_of(log: list[dict]) -> np.ndarray:
    return np.array([e["joint_pos"] for e in log if e["kind"] == "state"])


def with_params(twin: Twin, kp: float, kv: float, latency_s: float, jaw_delay_s: float) -> Twin:
    return dataclasses.replace(
        twin,
        servo=dataclasses.replace(twin.servo, kp=kp, kv=kv, latency_s=latency_s),
        release=dataclasses.replace(twin.release, jaw_delay_s=jaw_delay_s),
    )


def _twin_of(twin: Twin, theta: np.ndarray) -> Twin:
    return with_params(twin, twin.servo.kp * theta[0], twin.servo.kv * theta[0], *theta[1:] * MS)


def replay(twin: Twin, commands: Sequence[Command]) -> np.ndarray:
    """Joint positions the sim reads back for these commands."""
    return states_of(run(SimArm(ThrowSim(twin)), commands))


def fit(twin: Twin, logs: list[list[dict]]) -> dict:
    """Fit to one or more logs. Returns the fitted values (twin units), the joint-position RMS
    error (rad) before and after, and the number of sim runs. The logs need to move the arm and
    open the jaw, or the numbers that matter are not excited and the fit says so in `rms_*`."""
    jobs = [(commands_of(log), states_of(log)) for log in logs]
    runs = 0

    def residual(theta: np.ndarray) -> np.ndarray:
        nonlocal runs
        t = _twin_of(twin, theta)
        out = []
        for cmds, seen in jobs:
            runs += 1
            out.append((replay(t, cmds) - seen).ravel())
        return np.concatenate(out)

    def rms(theta: np.ndarray) -> float:
        return float(np.sqrt(np.mean(residual(theta) ** 2)))

    before = rms(START)
    sol = least_squares(
        residual,
        START,
        bounds=(LOWER, UPPER),
        diff_step=FD_STEP,
        x_scale=np.array([1, 20, 20]),
        ftol=1e-12,
        xtol=1e-12,
        gtol=1e-12,
    )
    fitted = _twin_of(twin, sol.x)
    dof = max(1, sol.fun.size - sol.x.size)
    cov = np.linalg.pinv(sol.jac.T @ sol.jac) * float(sol.fun @ sol.fun) / dof
    stderr = np.sqrt(np.diag(cov))  # one sigma, in the units of START
    return {
        "stderr": {
            "gain_ratio": float(stderr[0]),
            "latency_s": stderr[1] * MS,
            "jaw_delay_s": stderr[2] * MS,
        },  # fmt: skip
        "gain_ratio": float(sol.x[0]),
        "kp": fitted.servo.kp,
        "kv": fitted.servo.kv,
        "latency_s": fitted.servo.latency_s,
        "jaw_delay_s": fitted.release.jaw_delay_s,
        "rms_before_rad": before,
        "rms_after_rad": rms(sol.x),
        "sim_runs": runs,
    }
