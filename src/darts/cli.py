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
    report, best = sweep(
        twin, seed=args.seed, maxiter=args.maxiter, popsize=args.popsize, robust=args.robust
    )
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


def _policy(name: str):
    from darts.policies import POLICIES

    return POLICIES[name] if name in POLICIES else _load_policy(name)


def _load_policy(path: str):
    if path.endswith(".json"):  # a fitted base-throw map from `darts basemap`
        from darts.basemap import load_basemap_policy

        return load_basemap_policy(path)
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
        args.eval_every, args.max_seconds, args.n_steps, args.batch_size,
    )  # fmt: skip
    print(json.dumps(m, indent=2))
    return 0  # the Q13 verdict is in metrics.json; a finished run is not a failure


def _basemap(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    from darts.basemap import run

    m = run(load_twin(args.twin), args.targets, args.budget, args.workers, args.rounds, args.seed,
            Path(args.out), args.max_seconds)  # fmt: skip
    print(json.dumps(m, indent=2))
    return 0 if m["fit"] else 1


def _eval(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    from darts.env import DartThrowEnv, ObsNoise
    from darts.evaluate import evaluate

    noise = ObsNoise.from_estimator_json(args.obs_noise) if args.obs_noise else None
    env = DartThrowEnv(load_twin(args.twin), noise=noise)
    seeds = list(range(args.seed, args.seed + args.n))
    policy = _policy(args.policy)
    result = evaluate(env, policy, seeds) | {"policy": args.policy}
    print(json.dumps(result, indent=2))
    return 0 if result["meets_q13"] else 1


def _replay(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    from darts.env import DartThrowEnv
    from darts.interface import decode_action
    from darts.render import render_throw

    twin = load_twin(args.twin)
    env = DartThrowEnv(twin)
    _, info = env.reset(seed=args.seed)
    params, _ = decode_action(_policy(args.policy)(env.state(), np.random.default_rng(args.seed)))
    r = render_throw(twin, params, Path(args.out))
    ty, tz = info["target_yz_m"]
    print(f"target ({ty:+.3f}, {tz:+.3f}) m from centre; stuck={r.stuck} score={r.score}")
    print(f"video: {args.out}")
    return 0


def _game(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    from dataclasses import asdict

    from darts.match import play, sim_thrower

    twin = load_twin(args.twin)
    game, log = play(sim_thrower(twin, _policy(args.policy), args.seed))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = [{**r, "params": asdict(r["params"]), "hit": asdict(r["hit"])} for r in log]
    summary = {"remaining": game.remaining, "finished": game.finished, "turns": game.turns}
    (out / "game.json").write_text(json.dumps({**summary, "darts": rows}, indent=2))
    print(json.dumps(summary))
    if args.replay:
        from darts.render import render_game

        n = render_game(twin, log, out / "game.mp4", args.max_darts)
        print(f"video: {out / 'game.mp4'} ({n} of {len(log)} darts)")
    return 0


def _sysid(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    from darts.arm import read_log
    from darts.sysid import fit

    result = fit(load_twin(args.twin), [read_log(Path(p)) for p in args.logs])
    print(json.dumps(result, indent=2, default=float))
    return 0


def _ladder(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    import dataclasses

    from darts.ladder import farthest_robust, ladder, parse_power

    twin = load_twin(args.twin)
    twin = dataclasses.replace(twin, power=parse_power(args.power))
    rows = ladder(
        twin, args.distances, args.lean, args.workers, args.maxiter, args.popsize, args.seed
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ladder.json").write_text(json.dumps(rows, indent=2))
    print("dist  lean  sticks  miss   speed  angle  x     spin  arrival  outside bands")
    for r in rows:
        left = (
            f"{r['distance_m']:.2f}  {r['lean_m']:.1f}  {r['stick_rate']:6.0%}  {r['miss_m']:.2f}"
        )
        mid = (
            f"{r['release_speed_m_s']:5.2f}  {r['release_angle_deg']:4.0f}   {r['release_x_m']:.2f}"
        )
        right = f"{r['release_spin_rad_s']:4.0f}  {r['arrival_deg']:5.0f}"
        print(f"{left}  {mid}  {right}    {','.join(r['flags']) or '-'}")
    best = farthest_robust(rows)
    print(f"farthest robust distance: {best['distance_m'] if best else 'none'} m")
    return 0


def _visibility(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    from darts.env import DartThrowEnv
    from darts.interface import decode_action
    from darts.sim import ThrowSim, build_model
    from darts.visibility import MIN_VISIBLE, board_visibility

    twin = load_twin(args.twin)
    env, policy = DartThrowEnv(twin), _policy(args.policy)
    sim = ThrowSim(twin, build_model(twin, visual=True))
    worst = []
    for seed in range(args.seed, args.seed + args.n):
        env.reset(seed=seed)
        params, _ = decode_action(policy(env.state(), np.random.default_rng(seed)))
        r = board_visibility(twin, params, sim)
        worst.append((r["min"], seed, r["worst_frame"]))
        print(
            f"seed {seed}: board at least {r['min']:.1%} visible over {r['frames']} frames",
            flush=True,
        )
    low = min(worst)
    ok = low[0] >= MIN_VISIBLE
    print(
        f"worst: {low[0]:.1%} (seed {low[1]}, frame {low[2]}); "
        f"{'PASS' if ok else 'FAIL'} at {MIN_VISIBLE:.0%}"
    )
    return 0 if ok else 1


def _estimate(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    from darts.estimate import measure

    m = measure(load_twin(args.twin), args.n, args.seed, not args.clean)
    print(json.dumps(m, indent=2))
    return 0 if m["board_plane_error_m"]["p95"] <= args.max_p95 else 1


def _robust(args: argparse.Namespace) -> int:
    if not assets_available():
        print("SO-101 assets missing: run `make assets`", file=sys.stderr)
        return 2
    from darts.robust import robustness

    params = ThrowParams(**json.loads(Path(args.report).read_text())["best_params"])
    result = robustness(load_twin(args.twin), params, tuple(args.target))
    print(json.dumps(result, indent=2))
    return 0 if result["stuck_rate"] >= args.min_stuck else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="darts")
    sub = parser.add_subparsers(dest="cmd", required=True)
    throw = sub.add_parser("throw", help="run a throw")
    throw.add_argument("--scripted", action="store_true", required=True)
    throw.add_argument("--twin", default="twin.yaml")
    throw.add_argument("--seed", type=int, default=1)
    throw.add_argument("--maxiter", type=int, default=80)
    throw.add_argument("--popsize", type=int, default=20)
    throw.add_argument("--out", default="runs/v1")
    throw.add_argument("--no-video", action="store_true")
    throw.add_argument(
        "--robust",
        nargs="?",
        const="basic",
        choices=["basic", "wide"],
        help="average the cost over 6 (basic) or 18 (wide) aero and release-time variants",
    )
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
    ev.add_argument("--obs-noise", help="an estimator_error.json: blur what the policy sees")
    ev.add_argument("--twin", default="twin.yaml")
    tr = sub.add_parser("train", help="train a PPO residual on the hand-tuned throw")
    tr.add_argument("--steps", type=int, default=20_000)
    tr.add_argument("--n-envs", type=int, default=8)
    tr.add_argument("--seed", type=int, default=0)
    tr.add_argument("--scale", type=float, default=0.25, help="size of the learned correction")
    tr.add_argument("--n-steps", type=int, default=64, help="PPO rollout length per env")
    tr.add_argument("--batch-size", type=int, default=256, help="PPO minibatch size")
    tr.add_argument("--eval-every", type=int, default=10_000, help="steps between checkpoints")
    tr.add_argument("--max-seconds", type=float, help="stop gracefully (and save) after this long")
    tr.add_argument("--out", default="runs/train")
    tr.add_argument("--twin", default="twin.yaml")
    bm = sub.add_parser("basemap", help="solve a throw per board target and fit a base policy")
    bm.add_argument("--targets", type=int, default=80)
    bm.add_argument("--budget", type=int, default=4000, help="throws per target per round")
    bm.add_argument("--rounds", type=int, default=2, help="later rounds redo unsolved targets")
    bm.add_argument("--workers", type=int, default=4)
    bm.add_argument("--seed", type=int, default=0)
    bm.add_argument("--max-seconds", type=float, help="stop gracefully and fit what is solved")
    bm.add_argument("--out", default="runs/basemap")
    bm.add_argument("--twin", default="twin.yaml")
    ro = sub.add_parser("robust", help="how often a throw sticks across the aero guesses")
    ro.add_argument("--report", default="runs/v1/report.json", help="a throw report.json")
    ro.add_argument("--min-stuck", type=float, default=0.8, help="exit 1 below this stick rate")
    ro.add_argument(
        "--target",
        type=float,
        nargs=2,
        default=(0.0, 0.0),
        metavar=("Y", "Z"),
        help="aim offset from the board centre, m",
    )
    ro.add_argument("--twin", default="twin.yaml")
    vi = sub.add_parser(
        "visibility", help="board visibility from the mast camera over seeded throws"
    )
    vi.add_argument("--policy", default="hand", help="random, hand, or a basemap.json")
    vi.add_argument("--n", type=int, default=100)
    vi.add_argument("--seed", type=int, default=0)
    vi.add_argument("--twin", default="twin.yaml")
    ga = sub.add_parser("game", help="play a 501 game by strategy, optionally render the replay")
    ga.add_argument("--policy", default="hand", help="random, hand, or a basemap.json")
    ga.add_argument("--seed", type=int, default=0)
    ga.add_argument("--replay", action="store_true", help="render game.mp4 (slow, see docs)")
    ga.add_argument("--max-darts", type=int, help="render only the first N darts")
    ga.add_argument("--out", default="runs/game")
    ga.add_argument("--twin", default="twin.yaml")
    la = sub.add_parser("ladder", help="robust throw search at a ladder of board distances")
    la.add_argument("--distances", type=float, nargs="+", default=[0.5, 1.0, 1.4, 1.8, 2.1, 2.37])
    la.add_argument("--lean", type=float, nargs="+", default=[0.4, 0.2], help="first at every rung")
    la.add_argument(
        "--power", default="9:33.5:0.38:0.38", help="AK60-6: N.m:rad/s:shoulder kg:elbow kg"
    )
    la.add_argument("--workers", type=int, default=6)
    la.add_argument("--maxiter", type=int, default=60)
    la.add_argument("--popsize", type=int, default=20)
    la.add_argument("--seed", type=int, default=1)
    la.add_argument("--out", default="runs/ladder")
    la.add_argument("--twin", default="twin.yaml")
    si = sub.add_parser("sysid", help="fit servo gain, latency and jaw delay to arm logs, JSON out")
    si.add_argument("logs", nargs="+", help="JSON-lines logs written by `darts.arm.write_log`")
    si.add_argument("--twin", default="twin.yaml")
    es = sub.add_parser("estimate", help="detector error over random board poses, JSON out")
    es.add_argument("--n", type=int, default=100)
    es.add_argument("--seed", type=int, default=0)
    es.add_argument("--clean", action="store_true", help="no noise, blur or lighting change")
    es.add_argument("--max-p95", type=float, default=0.01, help="exit 1 above this, metres")
    es.add_argument("--twin", default="twin.yaml")
    rp = sub.add_parser("replay", help="render one policy throw at a seeded target to mp4")
    rp.add_argument("--policy", default="hand", help="random, hand, or a basemap.json")
    rp.add_argument("--seed", type=int, default=0)
    rp.add_argument("--out", default="runs/replay.mp4")
    rp.add_argument("--twin", default="twin.yaml")
    args = parser.parse_args(argv)
    return {
        "throw": _scripted,
        "drop": _drop,
        "eval": _eval,
        "train": _train,
        "basemap": _basemap,
        "robust": _robust,
        "visibility": _visibility,
        "estimate": _estimate,
        "game": _game,
        "sysid": _sysid,
        "ladder": _ladder,
        "replay": _replay,
    }[args.cmd](args)
