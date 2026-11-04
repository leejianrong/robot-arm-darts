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


def robustness(twin: Twin, params: ThrowParams) -> dict:
    """Throw once on each twin in the grid and report how often the dart sticks."""
    stuck, misses = [], []
    for fin, damp, drag in product(FIN_TORQUE, SPIN_DAMPING, DRAG):
        aero = dataclasses.replace(
            twin.aero,
            fin_torque_nm=twin.aero.fin_torque_nm * fin,
            spin_damping_nm_s=twin.aero.spin_damping_nm_s * damp,
            drag_kg_m=twin.aero.drag_kg_m * drag,
        )
        r = ThrowSim(dataclasses.replace(twin, aero=aero)).throw(params)
        stuck.append(r.stuck)
        misses.append(r.miss_m if r.stuck else np.inf)
    worst = max(misses)
    return {
        "n": len(stuck),
        "stuck_rate": float(np.mean(stuck)),
        "median_miss_m": float(np.median(misses)) if np.isfinite(np.median(misses)) else None,
        "worst_miss_m": float(worst) if np.isfinite(worst) else None,
    }
