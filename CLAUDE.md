# Robot Arm Darts

MuJoCo digital twin of an SO-101 arm that learns to throw a 10 g dart at a regulation-height board. Plan `PLAN.md`, build order `SLICES.md`, decisions `docs/adr/`, board Pandan `DART`.

## Status

Trust the code over the docs where they disagree, then fix the docs. Built: V1 (throw feasibility, `docs/v1-feasibility.md`). Next: V2. Feasible range is about 1.0 m, not the 1.5 m first planned.

## Commands

- `make install`, `make assets`, `make hooks` once per clone; `make check` is the pre-push gate; `make test-all` adds the integration layer.
- `make assets` fetches the pinned Menagerie SO-101 model into the gitignored `assets/menagerie/`. Integration tests skip without it.
- Python 3.12, uv. Training and rendering run on RunPod (ADR-0002); `darts throw` and `darts replay` render video, which needs `libosmesa6` and `MUJOCO_GL=osmesa` locally (about 80 s a clip), or EGL on a GPU pod.

## Rules that are not obvious

- Calibratable physical numbers live only in `twin.yaml` (ADR-0006). Solver contact settings in `sim.py` (`CONTACT_*`) are tuned, not physical; changing them lets the dart slip or creep (ADR-0008).
- A sweep or training result that looks too good (release speed over 6 m/s, hits from a downward release) is a solver or collision artifact until proven otherwise.
- Aero coefficients and the stick thresholds are guesses until real data exists (ADR-0005).
- Never print or commit the RunPod API key; it comes from the environment only.

## Workflow

Branch per slice off `main`, PR-only, merge when CI is green. Pushes and PRs do not trigger Actions on this repo (cause unknown); start CI with `gh workflow run ci.yml --ref <branch>`. Update README, CLAUDE.md and docs in the same PR as the change they describe.
