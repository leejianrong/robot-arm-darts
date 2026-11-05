"""`darts` command line entry point."""

import argparse
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np

from darts.sim import ThrowParams, ThrowSim, assets_available
from darts.sweep import sweep
from darts.twin import load_twin


def _scripted(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    twin = load_twin(args.twin)
    report, best = sweep(twin, seed=args.seed, maxiter=args.maxiter, popsize=args.popsize)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(asdict(report), indent=2))
    verdict = "YES" if report.reaches_board else "NO"
    print(f"max release speed seen : {report.max_release_speed_m_s:.2f} m/s")
    print(
        f"best throw             : release {report.best_release_speed_m_s:.2f} m/s at "
        f"{report.best_release_angle_deg:.0f} deg, {report.best_release_height_m:.2f} m high; "
        f"misses board centre by {report.best_miss_m:.2f} m"
    )
    print(
        f"release attitude       : {report.best_release_misalign_deg:.0f} deg off its direction "
        f"of travel, spinning {report.best_release_spin_rad_s:.1f} rad/s; arrives "
        f"{report.best_arrival_deg:.0f} deg off the board normal"
    )
    print(f"hits the board at {report.board_distance_m:.1f} m? : {verdict}")
    if not args.no_video:
        try:
            from darts.render import render_throw

            render_throw(twin, ThrowParams(**report.best_params), out / "throw.mp4")
            print(f"video                  : {out / 'throw.mp4'}")
        except Exception as e:  # no GL backend on this host is the usual cause
            print(f"video skipped ({type(e).__name__}: {e})", file=sys.stderr)
    return 0 if report.reaches_board else 1


def _drop(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    sim = ThrowSim(load_twin(args.twin))
    ang = math.radians(args.angle)
    vel = (args.speed * math.cos(ang), 0.0, args.speed * math.sin(ang))
    r = sim.launch((args.x, 0.0, args.height), vel)
    out = {"stuck": r.stuck, "score": r.score, "board_yz_m": r.board_yz, "short_m": r.shortfall_m}
    print(json.dumps(out))
    return 0 if r.stuck else 1


def _load_policy(path: str):
    from darts.train import load_policy

    return load_policy(path)


def _train(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    try:
        from darts.train import train
    except ImportError:
        print("training needs the extra: `uv sync --extra train`", file=sys.stderr)
        return 2
    m = train(
        load_twin(args.twin), args.steps, args.n_envs, args.seed, args.scale, Path(args.out),
        args.eval_every, args.max_seconds,
    )  # fmt: skip
    print(json.dumps(m, indent=2))
    return 0  # the Q13 verdict is in metrics.json; a finished run is not a failure


def _eval(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    from darts.env import DartThrowEnv
    from darts.evaluate import evaluate
    from darts.policies import POLICIES

    env = DartThrowEnv(load_twin(args.twin))
    seeds = list(range(args.seed, args.seed + args.n))
    policy = POLICIES[args.policy] if args.policy in POLICIES else _load_policy(args.policy)
    result = evaluate(env, policy, seeds) | {"policy": args.policy}
    print(json.dumps(result, indent=2))
    return 0 if result["meets_q13"] else 1


def _replay(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    from darts.env import DartThrowEnv
    from darts.interface import decode_action
    from darts.policies import POLICIES
    from darts.render import render_throw

    twin = load_twin(args.twin)
    env = DartThrowEnv(twin)
    _, info = env.reset(seed=args.seed)
    params, _ = decode_action(POLICIES[args.policy](env.state(), np.random.default_rng(args.seed)))
    r = render_throw(twin, params, Path(args.out))
    ty, tz = info["target_yz_m"]
    print(f"target ({ty:+.3f}, {tz:+.3f}) m from centre; stuck={r.stuck} score={r.score}")
    print(f"video: {args.out}")
    return 0


def _robust(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    from darts.robust import robustness

    params = ThrowParams(**json.loads(Path(args.report).read_text())["best_params"])
    result = robustness(load_twin(args.twin), params)
    print(json.dumps(result, indent=2))
    return 0 if result["stuck_rate"] >= args.min_stuck else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="darts")
    sub = parser.add_subparsers(dest="cmd", required=True)
    throw = sub.add_parser("throw", help="run a throw")
    throw.add_argument("--scripted", action="store_true", required=True)
    throw.add_argument("--twin", default="twin.yaml")
    throw.add_argument("--seed", type=int, default=1)
    throw.add_argument("--maxiter", type=int, default=60)
    throw.add_argument("--popsize", type=int, default=20)
    throw.add_argument("--out", default="runs/v1")
    throw.add_argument("--no-video", action="store_true")
    drop = sub.add_parser("drop", help="launch a dart in free flight, no arm")
    drop.add_argument("--speed", type=float, required=True, help="launch speed, m/s")
    drop.add_argument("--angle", type=float, required=True, help="degrees above horizontal")
    drop.add_argument("--x", type=float, default=0.3, help="launch distance from the base, m")
    drop.add_argument("--height", type=float, default=1.6, help="launch height, m")
    drop.add_argument("--twin", default="twin.yaml")
    ev = sub.add_parser("eval", help="evaluate a policy on seeded throws, JSON out")
    ev.add_argument("--policy", required=True, help="random, hand, or a policy.zip from `train`")
    ev.add_argument("--n", type=int, default=100)
    ev.add_argument("--seed", type=int, default=0, help="first seed; the list is seed..seed+n-1")
    ev.add_argument("--twin", default="twin.yaml")
    tr = sub.add_parser("train", help="train a PPO residual on the hand-tuned throw")
    tr.add_argument("--steps", type=int, default=20_000)
    tr.add_argument("--n-envs", type=int, default=8)
    tr.add_argument("--seed", type=int, default=0)
    tr.add_argument("--scale", type=float, default=0.25, help="size of the learned correction")
    tr.add_argument("--eval-every", type=int, default=10_000, help="steps between checkpoints")
    tr.add_argument("--max-seconds", type=float, help="stop gracefully (and save) after this long")
    tr.add_argument("--out", default="runs/train")
    tr.add_argument("--twin", default="twin.yaml")
    ro = sub.add_parser("robust", help="how often a throw sticks across the aero guesses")
    ro.add_argument("--report", default="runs/v1/report.json", help="a throw report.json")
    ro.add_argument("--min-stuck", type=float, default=0.8, help="exit 1 below this stick rate")
    ro.add_argument("--twin", default="twin.yaml")
    rp = sub.add_parser("replay", help="render one policy throw at a seeded target to mp4")
    rp.add_argument("--policy", choices=["random", "hand"], default="hand")
    rp.add_argument("--seed", type=int, default=0)
    rp.add_argument("--out", default="runs/replay.mp4")
    rp.add_argument("--twin", default="twin.yaml")
    args = parser.parse_args(argv)
    return {
        "throw": _scripted,
        "drop": _drop,
        "eval": _eval,
        "train": _train,
        "robust": _robust,
        "replay": _replay,
    }[args.cmd](args)
