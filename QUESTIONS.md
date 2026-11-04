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
