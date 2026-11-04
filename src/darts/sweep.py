"""Feasibility sweep: can the real servo limits put a 10 g dart on the board? (V1)"""

from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import differential_evolution

from darts.sim import THROW_JOINTS, ThrowParams, ThrowResult, ThrowSim, build_model
from darts.twin import Twin

LIMITS = {  # joint ranges from the Menagerie model, slightly inside
    "shoulder_lift": (-1.7, 1.7),
    "elbow_flex": (-1.65, 1.65),
    "wrist_flex": (-1.6, 1.6),
}
T_RELEASE = (0.0, 0.6)
# A real throw releases the dart nose-forward and nearly spinless. A tumbling dart can stick by
# luck of its phase on arrival (V2 found such throws), so the search penalises it and a throw only
# counts as a hit when the release is clean.
MAX_MISALIGN_RAD = 0.35
MAX_SPIN_RAD_S = 3.0
MISALIGN_PENALTY_M_PER_RAD = 0.3
SPIN_PENALTY_M_PER_RAD_S = 0.03


def decode(x: np.ndarray) -> ThrowParams:
    return ThrowParams(
        q_start=(float(x[0]), float(x[1]), float(x[2])),
        q_end=(float(x[3]), float(x[4]), float(x[5])),
        t_release_s=float(x[6]),
    )


def clean_release(r: ThrowResult) -> bool:
    return r.release_misalign_rad <= MAX_MISALIGN_RAD and r.release_spin_rad_s <= MAX_SPIN_RAD_S


def cost(r: ThrowResult) -> float:
    """Lower is better. Valid throws are ranked by miss distance plus a penalty for a tumbling
    release; others by how far short."""
    if not r.released or r.slipped_early or r.diverged or r.collided:
        return 100.0
    penalty = MISALIGN_PENALTY_M_PER_RAD * max(0.0, r.release_misalign_rad - MAX_MISALIGN_RAD)
    penalty += SPIN_PENALTY_M_PER_RAD_S * max(0.0, r.release_spin_rad_s - MAX_SPIN_RAD_S)
    if r.hit_board and not r.stuck:  # reached the face but bounced: worse than any stuck dart
        return 0.5 + r.miss_m + penalty
    if r.crossed_plane:
        return r.miss_m + penalty
    return 10.0 + r.shortfall_m + penalty


@dataclass
class Report:
    evaluations: int
    max_release_speed_m_s: float
    best_miss_m: float
    best_release_speed_m_s: float
    best_release_angle_deg: float
    best_release_height_m: float
    best_release_misalign_deg: float
    best_release_spin_rad_s: float
    best_crossed_plane: bool
    board_distance_m: float
    board_radius_m: float
    reaches_board: bool
    best_params: dict


def sweep(
    twin: Twin, seed: int = 0, maxiter: int = 60, popsize: int = 15
) -> tuple[Report, ThrowParams]:
    sim = ThrowSim(twin, build_model(twin))
    bounds = [LIMITS[j] for j in THROW_JOINTS] * 2 + [T_RELEASE]
    seen = {"n": 0, "max_speed": 0.0}

    def objective(x: np.ndarray) -> float:
        seen["n"] += 1
        r = sim.throw(decode(x))
        if r.released and not (r.slipped_early or r.diverged or r.collided):
            seen["max_speed"] = max(seen["max_speed"], r.release_speed_m_s)
        return cost(r)

    res = differential_evolution(
        objective, bounds, rng=seed, maxiter=maxiter, popsize=popsize, tol=1e-6, polish=False
    )
    best = decode(res.x)
    r = sim.throw(best)
    report = Report(
        evaluations=seen["n"],
        max_release_speed_m_s=seen["max_speed"],
        best_miss_m=r.miss_m,
        best_release_speed_m_s=r.release_speed_m_s,
        best_release_angle_deg=float(np.degrees(r.release_angle_rad)),
        best_release_height_m=r.release_height_m,
        best_release_misalign_deg=float(np.degrees(r.release_misalign_rad)),
        best_release_spin_rad_s=r.release_spin_rad_s,
        best_crossed_plane=r.crossed_plane,
        board_distance_m=twin.board.distance_m,
        board_radius_m=twin.board.radius_m,
        reaches_board=r.stuck
        and clean_release(r)
        and not (r.slipped_early or r.diverged or r.collided),
        best_params=asdict(best),
    )
    return report, best
