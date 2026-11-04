# Robot Arm Darts

SO-101 digital twin in MuJoCo that learns to throw a 10 g dart at a regulation-height board 1.0 m away. Plan: `PLAN.md`; slices: `SLICES.md`; decisions: `docs/adr/`. Board: Pandan `DART`.

## Build status

Trust the code over the docs where they disagree, then fix the docs. Slice V1 (feasibility sweep) built; no GL backend on the laptop, so videos render on RunPod or after `apt install libosmesa6`. `make assets` fetches the Menagerie model.

## Commands

- `make install` frozen install · `make check` pre-push gate (lint, pyright, fast tests) · `make test-all` adds integration
- `make hooks` once per clone installs the pre-push hook
- Python 3.12, uv-managed. Heavy training runs on RunPod, never the laptop (ADR-0002).

## Conventions

- Branch per slice off `main`, PR-only, CI green before merge. Commit only when asked.
- All calibratable physical numbers live in `twin.yaml` only (ADR-0006). No duplicates in code.
- Tests: unit under `tests/`, anything needing Menagerie assets or heavy sim is marked `integration`. Deterministic: seed everything.
- Secrets (RunPod key) come from the environment only; never print or commit.
