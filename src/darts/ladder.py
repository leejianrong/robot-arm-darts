"""Distance ladder (DART-35): how far can the power joints throw a dart that sticks robustly?

One robust search per board distance, then the 54-variant check on each result, with each row
flagged against what human throwers do (`docs/real-darts-range.md`, ADR-0009)."""

import dataclasses
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict

from darts.robust import robustness
from darts.sim import ThrowParams
from darts.sweep import LEAN_M, sweep
from darts.twin import Power, Twin

# Human releases, measured at 2.37 m (Huang et al. 2024): 5.9 m/s at about 16 degrees above
# horizontal; the bands are wide of that on purpose.
HUMAN_SPEED_M_S = (4.5, 7.0)
HUMAN_ANGLE_DEG = (10.0, 25.0)
STICK_BAR = 0.8  # share of the 54 aero and timing variants that must stick


def parse_power(spec: str) -> Power:
    """`torque N.m:no-load rad/s:shoulder kg:elbow kg`, as the pod job writes it."""
    t, w, ms, me = (float(x) for x in spec.split(":"))
    return Power(t, w, w, ms, me)


def band_flags(row: dict) -> list[str]:
    """Names of the human bands a result falls outside."""
    out = []
    lo, hi = HUMAN_SPEED_M_S
    if not lo <= row["release_speed_m_s"] <= hi:
        out.append("speed")
    lo, hi = HUMAN_ANGLE_DEG
    if not lo <= row["release_angle_deg"] <= hi:
        out.append("angle")
    if row["release_x_m"] > row["lean_m"] + 0.01:
        out.append("lean")
    return out


def run_rung(
    twin: Twin, distance_m: float, lean_m: float, maxiter: int, popsize: int, seed: int
) -> dict:
    t = dataclasses.replace(twin, board=dataclasses.replace(twin.board, distance_m=distance_m))
    report, best = sweep(t, seed, maxiter, popsize, robust="basic", lean_m=lean_m)
    check = robustness(t, best)
    row = {
        "distance_m": distance_m,
        "lean_m": lean_m,
        "miss_m": report.best_miss_m,
        "release_speed_m_s": report.best_release_speed_m_s,
        "release_angle_deg": report.best_release_angle_deg,
        "release_x_m": report.best_release_x_m,
        "release_spin_rad_s": report.best_release_spin_rad_s,
        "arrival_deg": report.best_arrival_deg,
        "stick_rate": check["stuck_rate"],
        "params": asdict(best),
    }
    return row | {"flags": band_flags(row), "robust": check["stuck_rate"] >= STICK_BAR}


def _job(args: tuple) -> dict:
    return run_rung(*args)


def ladder(
    twin: Twin,
    distances: list[float],
    leans: list[float],
    workers: int,
    maxiter: int = 60,
    popsize: int = 20,
    seed: int = 1,
) -> list[dict]:
    """One search per (distance, lean), in parallel. Only the first lean is run at every
    distance; any later lean is run at the farthest distance as a sensitivity check."""
    jobs = [(twin, d, leans[0], maxiter, popsize, seed) for d in distances]
    jobs += [(twin, distances[-1], x, maxiter, popsize, seed) for x in leans[1:]]
    with ProcessPoolExecutor(workers) as pool:
        return list(pool.map(_job, jobs))


def farthest_robust(rows: list[dict]) -> dict | None:
    ok = [r for r in rows if r["robust"] and r["lean_m"] == rows[0]["lean_m"]]
    return max(ok, key=lambda r: r["distance_m"]) if ok else None


__all__ = ["LEAN_M", "ThrowParams", "ladder", "farthest_robust", "band_flags", "parse_power"]
