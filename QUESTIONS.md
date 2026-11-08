# Questions

Statuses: `DECIDED` (user answered) · `ASSUMED` (default taken, correct it if wrong) · `FORK` (waiting on the user) · `DEFERRED` (not needed this milestone).

## Open forks

None. Round 1 closed.

## Register

| ID | Question | Status | Answer or default | Landed |
|----|----------|--------|-------------------|--------|
| F1 | Target arm | DECIDED | SO-101 | ADR-0001 |
| F2 | Simulator and compute | DECIDED | MuJoCo, all runs on RunPod (laptop too weak) | ADR-0002 |
| F3 | Dart realism | DECIDED | 10 g dart, about 1.5 m, realistic; revised after V1: 1.5 m and 1.2 m are unreachable at the servo velocity limit, so 1.0 m. Claude's model: drag plus restoring torque, geometric sticking | ADR-0005 |
| F4 | Dart pick-up | DECIDED | Out of scope. Magic reset between throws | PLAN §Scope |
| F5 | Policy input and camera role | DECIDED | Perfect state first, then camera, estimator, policy via a fixed state interface | ADR-0003, ADR-0004 |
| F6 | Camera mount | DECIDED | Fixed to base frame on a mast, never moves with the arm, never occluded | ADR-0007 |
| Q1 | Primary user | ASSUMED | You, solo, sim now, real arm later; no hardware yet | PLAN §Users |
| Q2 | Language / host | ASSUMED | Python 3.12 (3.13 dropped: wider wheel support for MuJoCo/SB3), WSL2 Linux, uv-managed | PLAN §Impl |
| Q3 | Dart sticking model | ASSUMED | Tip contact within board face: sticks if speed/angle ok, else bounce; score from tip point. Built in V2 as stop-at-first-contact, no weld (ADR-0005) | PLAN §Shape |
| Q4 | Dart flight aero | ASSUMED | Custom per-step drag + fin restoring torque | PLAN §Shape |
| Q5 | Config/state storage | ASSUMED | One `twin.yaml` of all calibratable params, versioned in git | ADR |
| Q6 | Real-robot interface | ASSUMED | Same `Arm` protocol for sim and hardware; LeRobot as the real driver | ADR |
| Q7 | Failure behaviour | ASSUMED | Out-of-limit action = clipped + flagged in info; sim divergence (NaN) = episode aborted, logged | PLAN |
| Q8 | Security/secrets | ASSUMED | RunPod API key is the one secret: read from env only, never logged, committed or echoed in CLI output | PLAN §Implementation |
| Q9 | Versioning | ASSUMED | `twin.yaml` has `schema_version`; migrations deferred | PLAN |
| Q10 | Deps/licences | ASSUMED | MuJoCo (Apache-2.0), menagerie SO-101 (Apache-2.0 per repo), Gymnasium (MIT), SB3/PPO (MIT); all offline | PLAN |
| Q11 | System identification tooling | DEFERRED | Interfaces built now; fitting needs real data | n/a |
| Q12 | Concurrency | ASSUMED | Single process, deterministic seeded sim; no multi-writer concerns | n/a |
| F7 | What does 2.37 m measure? | DECIDED | Base at the throw line, board 2.37 m from the base axis, hand may reach 0.4 m ahead of it (rules limit feet only; lean is ASSUMED) | ADR-0009 |
| F8 | When is the move to real range done? | DECIDED | Distance ladder finds the farthest rung with at least 80% sticks; twin moves there; 2.37 m stays the goal | ADR-0009 |
| F9 | Buying hardware | DECIDED | Not for the foreseeable future; gate is simulation only. First purchase later: one AK60-6 for a bench test | ADR-0009 |
| Q14 | Power joints | ASSUMED | AK60-6 V3 on shoulder_lift and elbow_flex, SO-101 links kept, datasheet numbers checked in DART-38 | ADR-0010 |
| Q15 | Real driver with CAN joints | DEFERRED | Mixed CAN and serial backend for `LeRobotArm` once hardware exists (DART-39) | ADR-0010 |
| Q16 | Human reference numbers | DECIDED | Measured at 2.37 m: release 5.9 m/s at 16 deg above horizontal, wrist 26 rad/s, elbow 8.5, shoulder 3.8; lean derived at about 0.7 m, plan uses 0.4 m. Bands: 4.5 to 7 m/s, 10 to 25 deg | docs/real-darts-range.md |
| Q13 | Success metric | ASSUMED | Mean tip error to commanded target (cm) over 100 seeded throws, domain-randomised | SLICES |

## Coverage

| Category | Covered by |
|----------|-----------|
| Primary user and actors | Q1 |
| Scope boundary | F3, F4 |
| Data model and identity | Q5 |
| State and storage | Q5 |
| Concurrency and conflict | Q12 |
| Interfaces and contracts | Q6, F5 |
| Failure behaviour | Q7 |
| External dependencies | F1, F2, Q10 |
| Runtime and deployment | Q2, F2 |
| Measurable success | Q13 |
| Security and secrets | Q8 |
| Versioning and migration | Q9 |
| Real range (2.37 m) | F7, F8, F9, Q14, Q15, Q16 |
