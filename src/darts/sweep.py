"""Feasibility sweep: can the real servo limits put a 10 g dart on the board? (V1)"""

import math
from dataclasses import asdict, dataclass, replace
from itertools import product

import numpy as np
from scipy.optimize import differential_evolution, minimize

from darts.robust import DRAG, FIN_TORQUE, RELEASE_JITTER_S, SPIN_DAMPING, aero_variant
from darts.sim import THROW_JOINTS, ThrowParams, ThrowResult, ThrowSim, build_model
from darts.twin import Twin

LIMITS = {  # joint ranges from the Menagerie model, slightly inside
    "shoulder_lift": (-1.7, 1.7),
    "elbow_flex": (-1.65, 1.65),
    "wrist_flex": (-1.6, 1.6),
}
T_RELEASE = (0.0, 0.45)  # the cross grip holds about this long in a swing
# A fast hand always rotates, so the dart leaves spinning and tumbles in flight. What matters is
# its attitude on arrival: stick needs the axis within the board's stick angle, and the search
# keeps a margin inside it so the throw survives small errors in flight time and aero.
MAX_ARRIVAL_RAD = 0.7
ARRIVAL_PENALTY_M_PER_RAD = 0.3
SPEED_MARGIN = 1.15  # aim this far above the stick speed
SPEED_PENALTY_M_PER_M_S = 0.15
BOUNCE_PENALTY_M = 0.2  # small enough that touching the face beats skimming past its rim


# Release attitudes that only work when everything goes right: tail-first, spinning fast, or a
# release speed past what the solver is trusted for (CLAUDE.md).
MAX_MISALIGN_RAD = math.pi / 2
MAX_SPIN_RAD_S = 15.0
MAX_RELEASE_SPEED_M_S = 6.0
MISALIGN_PENALTY_M = 0.3
SPIN_PENALTY_M_PER_RAD_S = 0.01
RELEASE_SPEED_PENALTY_M_PER_M_S = 0.2
VARIANT_COST_CAP = 13.0  # above 10 + any shortfall, so falling short keeps its gradient; only a
# crashed throw (100) is capped, so one bad variant cannot drown the average
# (fin, damping, drag multipliers, release-time jitter s): the nominal throw, early and late
# release, and the two aero corners. A subset of `darts robust`'s 54 so a search stays affordable.
BASIC_VARIANTS = (
    (1.0, 1.0, 1.0, 0.0),
    (1.0, 1.0, 1.0, -0.01),
    (1.0, 1.0, 1.0, 0.01),
    (0.5, 0.3, 0.5, 0.0),
    (2.0, 3.0, 1.5, 0.0),
    (0.5, 3.0, 1.5, 0.01),
)
# Every fin x damping x drag combination of `darts robust`, with the jitter cycling through its
# three values: 18 of the 54, each aero corner seen with early, on-time and late release.
WIDE_VARIANTS = tuple(
    (f, d, g, RELEASE_JITTER_S[i % 3])
    for i, (f, d, g) in enumerate(product(FIN_TORQUE, SPIN_DAMPING, DRAG))
)
ROBUST_VARIANTS = {"basic": BASIC_VARIANTS, "wide": WIDE_VARIANTS}


def release_penalty(r: ThrowResult) -> float:
    """Metres of penalty for releases that the 54-variant check later shows to be knife-edge."""
    return (
        MISALIGN_PENALTY_M * (r.release_misalign_rad > MAX_MISALIGN_RAD)
        + SPIN_PENALTY_M_PER_RAD_S * max(0.0, r.release_spin_rad_s - MAX_SPIN_RAD_S)
        + RELEASE_SPEED_PENALTY_M_PER_M_S * max(0.0, r.release_speed_m_s - MAX_RELEASE_SPEED_M_S)
    )


def decode(x: np.ndarray) -> ThrowParams:
    return ThrowParams(
        q_start=(float(x[0]), float(x[1]), float(x[2])),
        q_end=(float(x[3]), float(x[4]), float(x[5])),
        t_release_s=float(x[6]),
    )


def square_arrival(r: ThrowResult) -> bool:
    return r.arrival_angle_rad <= MAX_ARRIVAL_RAD


def throw_penalty(r: ThrowResult, stick_speed: float = 2.0) -> float:
    """Metres of penalty for arriving at a slant, slower than the stick speed (with a margin), or
    bouncing. Shared by the search cost and the training reward, so both want the same throw."""
    penalty = ARRIVAL_PENALTY_M_PER_RAD * max(0.0, r.arrival_angle_rad - MAX_ARRIVAL_RAD)
    penalty += SPEED_PENALTY_M_PER_M_S * max(0.0, stick_speed * SPEED_MARGIN - r.arrival_speed_m_s)
    return penalty + (BOUNCE_PENALTY_M if r.hit_board and not r.stuck else 0.0)


def cost(r: ThrowResult, stick_speed: float = 2.0, target_yz: tuple[float, float] = (0.0, 0.0)):
    """Lower is better. Valid throws are ranked by distance from `target_yz` (board-plane lateral
    and height offsets from the centre) plus `throw_penalty`; others by how far short."""
    if not r.released or r.slipped_early or r.diverged or r.collided:
        return 100.0
    if not r.crossed_plane:
        return 10.0 + r.shortfall_m
    miss = float(np.hypot(r.board_yz[0] - target_yz[0], r.board_yz[1] - target_yz[1]))
    return miss + throw_penalty(r, stick_speed)


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
    best_arrival_deg: float
    best_crossed_plane: bool
    board_distance_m: float
    board_radius_m: float
    reaches_board: bool
    best_params: dict


def sweep(
    twin: Twin, seed: int = 0, maxiter: int = 60, popsize: int = 15, robust: str | None = None
) -> tuple[Report, ThrowParams]:
    """Search for a throw. With `robust` ("basic" or "wide"), the cost averages over that set of
    ROBUST_VARIANTS and adds `release_penalty`, so the answer survives aero guesses and jitter."""
    sim = ThrowSim(twin, build_model(twin))
    variants = [
        (ThrowSim(aero_variant(twin, f, d, g), build_model(twin)), j)
        for f, d, g, j in ROBUST_VARIANTS.get(robust, ())
    ]
    bounds = [LIMITS[j] for j in THROW_JOINTS] * 2 + [T_RELEASE]
    seen = {"n": 0, "max_speed": 0.0}

    def objective(x: np.ndarray) -> float:
        seen["n"] += 1
        r = sim.throw(decode(x))
        if r.released and not (r.slipped_early or r.diverged or r.collided):
            seen["max_speed"] = max(seen["max_speed"], r.release_speed_m_s)
        if not robust:
            return cost(r, twin.board.stick_min_speed_m_s)
        costs = []
        for vsim, jit in variants:
            v = vsim.throw(replace(decode(x), t_release_s=float(x[6]) + jit))
            costs.append(
                min(cost(v, twin.board.stick_min_speed_m_s) + release_penalty(v), VARIANT_COST_CAP)
            )
        return float(np.mean(costs))

    res = differential_evolution(
        objective, bounds, rng=seed, maxiter=maxiter, popsize=popsize, tol=1e-6, polish=False
    )
    # DE alone stalls short of the target on this chaotic cost; a local polish closes the gap.
    polished = minimize(
        objective, res.x, method="Nelder-Mead", bounds=bounds, options={"maxiter": 600}
    )
    best = decode(polished.x if polished.fun < res.fun else res.x)
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
        best_arrival_deg=float(np.degrees(r.arrival_angle_rad)),
        best_crossed_plane=r.crossed_plane,
        board_distance_m=twin.board.distance_m,
        board_radius_m=twin.board.radius_m,
        reaches_board=r.stuck
        and square_arrival(r)
        and not (r.slipped_early or r.diverged or r.collided),
        best_params=asdict(best),
    )
    return report, best
