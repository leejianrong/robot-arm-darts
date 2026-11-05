"""A base throw for every target: solve a throw per target on the board, then fit a smooth map.

The hand policy fires one throw at every target, so it lands low and ignores height. Here a
search finds a throw that sticks near each of N targets (in parallel, warm-started from the best
centre throw and then from solved neighbours), and a cubic regression turns the solutions
into a policy: target -> the eight throw numbers. PPO can then learn a small correction on top.
"""

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from darts.env import DartThrowEnv
from darts.evaluate import evaluate
from darts.interface import PAN_LIMIT_RAD, State, encode_action
from darts.policies import _BEST, Policy, hand_tuned_policy
from darts.robust import aero_variant
from darts.sim import ThrowParams, ThrowSim, build_model
from darts.sweep import LIMITS, T_RELEASE, cost
from darts.twin import Twin

HELD_OUT_SEEDS = list(range(10_000, 10_100))
AERO_CORNERS = ((0.5, 0.3, 0.5), (2.0, 3.0, 1.5))
ACCEPT_M = 0.06  # a solution must stick within this of its target to enter the fit
LOW = np.array([lo for lo, _ in LIMITS.values()] * 2 + [T_RELEASE[0], -PAN_LIMIT_RAD])
HIGH = np.array([hi for _, hi in LIMITS.values()] * 2 + [T_RELEASE[1], PAN_LIMIT_RAD])

_worker: dict = {}


def board_targets(twin: Twin, n: int) -> np.ndarray:
    """n points spread over the board disc (a sunflower spiral), as (y, z) offsets from centre."""
    k = np.arange(n) + 0.5
    r = 0.9 * twin.board.radius_m * np.sqrt(k / n)
    a = k * np.pi * (3.0 - np.sqrt(5.0))
    return np.column_stack([r * np.sin(a), r * np.cos(a)])


def _init_worker(twin: Twin) -> None:
    _worker["twin"], _worker["sim"] = twin, ThrowSim(twin, build_model(twin))


def start_vector(twin: Twin, y: float) -> np.ndarray:
    """The best centre throw, turned to face a target at lateral offset y."""
    pan = -float(np.arctan2(y, twin.board.distance_m))
    return np.array([*_BEST.q_start, *_BEST.q_end, _BEST.t_release_s, pan])


def _throw(x: np.ndarray):
    return _worker["sim"].throw(
        ThrowParams(tuple(x[:3]), tuple(x[3:6]), float(x[6]), float(x[7]))  # type: ignore[arg-type]
    )


def solve_target(job: tuple) -> dict:
    """Find a throw that sticks near one target: jittered starts, then Nelder-Mead on the best."""
    idx, target, x0, budget, seed = job
    twin: Twin = _worker["twin"]
    rng = np.random.default_rng(seed)
    t0, stick_v = time.time(), twin.board.stick_min_speed_m_s
    n = 0

    def f(x: np.ndarray) -> float:
        nonlocal n
        n += 1
        return cost(_throw(np.clip(x, LOW, HIGH)), stick_v, tuple(target))

    span = HIGH - LOW
    starts = [np.clip(x0 + rng.normal(0, 0.03, 8) * span, LOW, HIGH) for _ in range(budget // 4)]
    starts = sorted([x0, *starts], key=f)[:3]
    best_x, best_c = starts[0], f(starts[0])
    for s in starts:
        res = minimize(f, s, method="Nelder-Mead", bounds=list(zip(LOW, HIGH, strict=True)),
                       options={"maxfev": max(budget // 4, 20)})  # fmt: skip
        if res.fun < best_c:
            best_x, best_c = np.clip(res.x, LOW, HIGH), float(res.fun)
    r = _throw(best_x)
    miss = float(np.hypot(r.board_yz[0] - target[0], r.board_yz[1] - target[1]))
    return {
        "idx": idx, "target": list(map(float, target)), "x": best_x.tolist(), "cost": best_c,
        "stuck": bool(r.stuck), "miss_m": miss,
        "arrival_deg": float(np.degrees(r.arrival_angle_rad)),
        "evals": n, "seconds": round(time.time() - t0, 1),
    }  # fmt: skip


DEGREE = 3  # quadratic left the top rim (z > +11 cm) unreachable: 89% stuck vs 99% for cubic


def features(y: float, h: float, degree: int = DEGREE) -> np.ndarray:
    return np.array([y**i * h**j for i in range(degree + 1) for j in range(degree + 1 - i)])


def fit(solved: list[dict], centre_h: float = 0.0) -> dict | None:
    """Least-squares polynomial map from target (y, z) to the eight throw numbers, or None."""
    ok = [s for s in solved if s["stuck"] and s["miss_m"] <= ACCEPT_M]
    if len(ok) < 12:
        return None
    a = np.array([features(*s["target"]) for s in ok])
    x = np.array([s["x"] for s in ok])
    coef, *_ = np.linalg.lstsq(a, x, rcond=None)
    resid = a @ coef - x
    return {
        "coef": coef.T.tolist(), "centre_h": centre_h, "n_fit": len(ok),
        "fit_rms": float(np.sqrt(np.mean(resid**2))),
    }  # fmt: skip


def basemap_policy(fitted: dict) -> Policy:
    coef = np.array(fitted["coef"])
    degree = next(d for d in range(1, 8) if len(features(0.0, 0.0, d)) == coef.shape[1])

    def policy(state: State, rng: np.random.Generator) -> np.ndarray:
        y, h = float(state.target_in_base[1]), float(state.target_in_base[2]) - fitted["centre_h"]
        x = np.clip(coef @ features(y, h, degree), LOW, HIGH)
        p = ThrowParams(tuple(x[:3]), tuple(x[3:6]), float(x[6]), float(x[7]))  # type: ignore[arg-type]
        return encode_action(p)

    return policy


def load_basemap_policy(path: str | Path) -> Policy:
    return basemap_policy(json.loads(Path(path).read_text()))


def run(twin: Twin, n_targets: int, budget: int, workers: int, rounds: int, seed: int,
        out: Path, max_seconds: float | None) -> dict:  # fmt: skip
    """Solve every target in parallel (progress on stdout, one jsonl row each), fit, evaluate."""
    out.mkdir(parents=True, exist_ok=True)
    targets = board_targets(twin, n_targets)
    centre_h = twin.board.centre_height_m - twin.mount.height_m
    solved: dict[int, dict] = {}
    start, stopped = time.time(), ""
    # Targets are targets in (y, z) from the board centre; the env's state height is centre_h + z.
    with ProcessPoolExecutor(workers, initializer=_init_worker, initargs=(twin,)) as ex:
        for rnd in range(rounds):
            todo = [i for i in range(n_targets) if i not in solved or not _good(solved[i])]
            good = [s for s in solved.values() if _good(s)]
            jobs = []
            for i in todo:
                x0 = start_vector(twin, targets[i][0])
                if good:  # warm start from the nearest target that already sticks
                    near = min(good, key=lambda s: np.hypot(*(np.array(s["target"]) - targets[i])))
                    x0 = np.array(near["x"])
                jobs.append((i, targets[i], x0, budget, seed * 1000 + rnd * 100 + i))
            print(f"STAGE round {rnd + 1}/{rounds}: {len(jobs)} targets", flush=True)
            futs = [ex.submit(solve_target, j) for j in jobs]
            for fut in as_completed(futs):
                if fut.cancelled():
                    continue
                s = fut.result()
                if s["idx"] not in solved or s["cost"] < solved[s["idx"]]["cost"]:
                    solved[s["idx"]] = s
                with (out / "solutions.jsonl").open("a") as f:
                    f.write(json.dumps(s) + "\n")
                ok = sum(_good(v) for v in solved.values())
                print(f"PROGRESS round={rnd + 1} solved={len(solved)}/{n_targets} good={ok} "
                      f"last_miss_cm={s['miss_m'] * 100:.1f} stuck={s['stuck']} "
                      f"evals={s['evals']} took={s['seconds']}s", flush=True)  # fmt: skip
                if max_seconds and time.time() - start > max_seconds and not stopped:
                    stopped = f"time budget {max_seconds:.0f}s used"
                    print(f"ABORT {stopped}", flush=True)
                    for g in futs:
                        g.cancel()
            if stopped:
                break
    fitted = fit(list(solved.values()), centre_h)
    metrics: dict = {
        "config": {"targets": n_targets, "budget": budget, "workers": workers, "rounds": rounds},
        "seconds": round(time.time() - start, 1), "aborted": stopped or None,
        "solved": len(solved), "good": sum(_good(v) for v in solved.values()),
        "fit": None if fitted is None else {k: v for k, v in fitted.items() if k != "coef"},
    }  # fmt: skip
    if fitted is None:
        print("ERROR too few good targets to fit", flush=True)
    else:
        (out / "basemap.json").write_text(json.dumps(fitted))
        policy = basemap_policy(fitted)
        metrics["baseline_hand"] = evaluate(DartThrowEnv(twin), hand_tuned_policy, HELD_OUT_SEEDS)
        metrics["held_out"] = evaluate(DartThrowEnv(twin), policy, HELD_OUT_SEEDS)
        metrics["aero_corners"] = {
            str(c): evaluate(DartThrowEnv(aero_variant(twin, *c)), policy, HELD_OUT_SEEDS[:30])
            for c in AERO_CORNERS
        }  # fmt: skip
        ho, hand = metrics["held_out"], metrics["baseline_hand"]
        print(f"RESULT held_out on_board={ho['on_board_rate']} median_m={ho['median_tip_error_m']} "
              f"hand_on_board={hand['on_board_rate']}", flush=True)  # fmt: skip
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def _good(s: dict) -> bool:
    return bool(s["stuck"] and s["miss_m"] <= ACCEPT_M)
