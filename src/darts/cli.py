"""`darts` command line entry point."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

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
    print(f"hits the board at {report.board_distance_m:.1f} m? : {verdict}")
    if not args.no_video:
        try:
            from darts.render import render_throw

            sim = ThrowSim(twin)
            render_throw(
                sim, ThrowParams(**{k: v for k, v in report.best_params.items()}), out / "throw.mp4"
            )
            print(f"video                  : {out / 'throw.mp4'}")
        except Exception as e:  # no GL backend on this host is the usual cause
            print(f"video skipped ({type(e).__name__}: {e})", file=sys.stderr)
    return 0 if report.reaches_board else 1


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
    args = parser.parse_args(argv)
    return _scripted(args)
