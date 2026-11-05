"""How much a throw depends on the guessed aerodynamic numbers: a local check before pod runs."""

import dataclasses
from itertools import product

import numpy as np

from darts.sim import ThrowParams, ThrowSim
from darts.twin import Twin

# Multipliers on the aero guesses in twin.yaml; the real dart is somewhere inside these ranges.
FIN_TORQUE = (0.5, 1.0, 2.0)
SPIN_DAMPING = (0.3, 1.0, 3.0)
DRAG = (0.5, 1.5)
RELEASE_JITTER_S = (-0.01, 0.0, 0.01)  # the jaw opens a little early or late on a real servo


def aero_variant(twin: Twin, fin: float, damp: float, drag: float) -> Twin:
    """The twin with its aero guesses scaled by these multipliers."""
    a = twin.aero
    return dataclasses.replace(
        twin,
        aero=dataclasses.replace(
            a,
            fin_torque_nm=a.fin_torque_nm * fin,
            spin_damping_nm_s=a.spin_damping_nm_s * damp,
            drag_kg_m=a.drag_kg_m * drag,
        ),
    )


def robustness(twin: Twin, params: ThrowParams) -> dict:
    """Throw once per aero guess and release-time jitter, and report how often the dart sticks."""
    stuck, misses = [], []
    for fin, damp, drag, jit in product(FIN_TORQUE, SPIN_DAMPING, DRAG, RELEASE_JITTER_S):
        p = dataclasses.replace(params, t_release_s=params.t_release_s + jit)
        r = ThrowSim(aero_variant(twin, fin, damp, drag)).throw(p)
        stuck.append(r.stuck)
        misses.append(r.miss_m if r.stuck else np.inf)
    worst = max(misses)
    return {
        "n": len(stuck),
        "stuck_rate": float(np.mean(stuck)),
        "median_miss_m": float(np.median(misses)) if np.isfinite(np.median(misses)) else None,
        "worst_miss_m": float(worst) if np.isfinite(worst) else None,
    }
