# Robot Arm Darts

MuJoCo digital twin of an SO-101 arm that learns to throw a 10 g dart at a regulation-height board. Plan `PLAN.md`, build order `SLICES.md`, decisions `docs/adr/`, board Pandan `DART`.

## Status

Trust the code over the docs where they disagree, then fix the docs. Built through V4 minus a trained policy. The board is at 0.5 m: the cross grip (wrist roll 90°) at the 4.5 rad/s servo limit reaches no further (`docs/v1-feasibility.md`). Training is on hold until throws are believable and robust; run `darts robust` before trusting any hit.

## Commands

- `make install`, `make assets`, `make hooks` once per clone; `make check` is the pre-push gate; `make test-all` adds the integration layer.
- `make assets` fetches the pinned Menagerie SO-101 model into the gitignored `assets/menagerie/`. Integration tests skip without it.
- Python 3.12, uv. Training and rendering run on RunPod (ADR-0002); `darts throw` and `darts replay` render video, which needs `libosmesa6` and `MUJOCO_GL=osmesa` locally (about 80 s a clip), or EGL on a GPU pod.

- `scripts/pod_train.sh` runs `JOB=train` (default) or `JOB=basemap` (the per-target base-throw search; CPU only, no torch). `scripts/rp_guard.py` enforces a spend cap from the laptop: run it detached before any pod, with the key in the environment.
- Training: `uv sync --extra train` (CPU torch + SB3), then `scripts/pod_train.sh` runs it on RunPod and needs `RUNPOD_API_KEY` and `RP_MAX_HOURLY_USD` in the environment. Do not train on the laptop: 7 GB RAM, it swaps and the machine lags. A run writes `metrics.jsonl` and a checkpoint every `--eval-every` steps, prints `EVAL` lines, and stops itself with an `ABORT <why>` line (diverged above 1%, on-board rate 25 points under the hand throw, RAM above 90%, time budget) while still saving and publishing.

## Rules that are not obvious

- Calibratable physical numbers live only in `twin.yaml` (ADR-0006). Solver contact settings in `sim.py` (`CONTACT_*`) are tuned, not physical; changing them lets the dart slip or creep (ADR-0008).
- The dart is held across the fingers (`GRIP_*` in `sim.py`); the pinch creeps out after about 0.45 s, so releases come before that. Judge throws by arrival angle and `darts robust`, not by release attitude: a fast hand always spins the dart.
- A sweep or training result that looks too good (release speed over 6 m/s, hits from a downward release) is a solver or collision artifact until proven otherwise.
- A training result with a high on-board rate and a low stuck rate is farming bounces (the 20k pilot did: 100% / 0%). Reward and `tip_error_m` count only darts that stick.
- Aero coefficients and the stick thresholds are guesses until real data exists (ADR-0005).
- Never print or commit the RunPod API key; it comes from the environment only.

## Workflow

Branch per slice off `main`, PR-only, merge when CI is green. Pushes and PRs do not trigger Actions on this repo (cause unknown); start CI with `gh workflow run ci.yml --ref <branch>`. Update README, CLAUDE.md and docs in the same PR as the change they describe.
