# Robot Arm Darts: Plan

Status: agreed (round 1 closed) · Milestone: MVP, sim only

## Problem

You want a robot arm that plays darts, and you want to get there by training in simulation and moving to a real arm later. You have no arm yet and little local compute, so the sim has to be a digital twin: every physical parameter lives in one place, so that when the arm arrives you tune numbers to match it instead of rewriting code.

Darts is a hard test for this. The dart is light, the release timing is sub-100 ms, and a few millimetres at the board change the score. Sim-to-real gaps in servo response, gripper release and dart aerodynamics show up directly as misses.

## Solution

A MuJoCo simulation of an SO-101 arm (5-DOF plus a two-jaw gripper) holding a 10 g dart, 1.0 m from a regulation-height dartboard (centre 1.73 m, arm on a stand). A policy takes the target (a board segment) and outputs a one-shot throw: a short parametrised joint trajectory plus a release time. The dart flies with simple aerodynamics, sticks in the board or bounces, and a scorer reads the score from the tip position.

Training runs headless on RunPod. The laptop only edits code and watches rendered videos.

Perception is modular. At first the policy gets perfect state. Later a base-mounted virtual camera feeds a state estimator, which outputs the same state interface, and the policy is unchanged.

## Users and actors

- **You**, solo: author, trainer and eventual owner of the real arm. Primary.
- **Coding agents** building from SLICES.md. When agent output and your decision disagree, you win.
- **RunPod pods**, as the compute actor. Pods are disposable and billed per hour (see Testing approach for the teardown rule).
- **The real SO-101** is a future actor, not in this milestone. It is represented by a hardware seam (S7).

## Scope

**In this milestone.**
- SO-101 sim model with realistic actuator limits, taken from the Menagerie model and driven by `twin.yaml`.
- A 10 g dart held by jaw friction (ADR-0008) at the start of each throw, thrown 1.0 m to a regulation-height board.
- A dartboard with geometric scoring, and 501 game logic.
- A policy trained on perfect state, then on noisy state, then on estimated state.
- A fixed, unoccluded virtual camera, and a board-pose estimator.
- Domain randomisation of twin parameters.
- A hardware-ready seam, and a system-identification fit demonstrated on synthetic data.

**Out.**
- Picking a dart up (decided F4). The dart is magically reset into the gripper between throws. Out because it is a separate grasping problem.
- Real hardware, real servo calibration, real throws. No arm yet.
- End-to-end pixel-to-action RL. The modular pipeline replaces it.
- Dart flight through fluid simulation. A drag and restoring-torque model is enough.
- Multi-arm, moving boards, opponents.

## Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | Sim-trained policy hits a commanded board target accurately, with parameters kept in one twin-tunable file | Core goal |
| R1 | SO-101 model obeys real actuator limits (position, velocity, torque, gripper release timing) | Must-have |
| R2 | Dart physics: 10 g, flight with drag and stabilising torque, sticks or bounces, scored by tip position | Must-have |
| R3 | Training and evaluation are reproducible (seeded, deterministic) and run headless on RunPod | Must-have |
| R4 | Policy interface is a state vector, and perfect state and estimated state are interchangeable | Must-have |
| R5 | Virtual camera fixed to the base frame, board visible throughout every throw | Must-have |
| R6 | Policy is robust to twin-parameter randomisation | Must-have |
| R7 | The sim and a real arm share one `Arm` protocol, and twin params can be fitted from logged trajectories | Must-have |
| R8 | A full 501 game is playable by the agent | Nice-to-have |

## Shape

| Part | Mechanism | ADR |
|------|-----------|-----|
| S1 | SO-101 MJCF from Menagerie, wrapped by a loader that overlays `twin.yaml` (gains, limits, masses, friction, latency) | 0001, 0006 |
| S2 | Dart as a free body, with per-step drag force and fin restoring torque applied through `xfrc_applied` | 0005 |
| S3 | Board: a plane with a disc and ring geometry. On tip contact inside the face, a weld constraint is added if speed and angle allow, otherwise a bounce. Score from the tip point | 0005 |
| S4 | Throw action: joint waypoints parametrised by about 8 numbers plus a release time, executed through the actuators at the control rate | 0004 |
| S5 | Gymnasium env `DartThrowEnv`: obs is the state interface, action is the throw params, reward is negative tip-to-target distance | 0003, 0004 |
| S6 | Camera: a MuJoCo camera on a rigid mast from the base frame, rendered headless (EGL). Estimator maps image to board pose and then target in the base frame | 0003, 0007 |
| S7 | `Arm` protocol (`set_targets`, `read_state`, `open_gripper`) with a `SimArm` backend and a `LeRobotArm` backend stub. A sysid fitter minimises trajectory error | 0006 |
| S8 | RunPod job runner: bootstrap, train, pull artifacts, guaranteed teardown | 0002 |

## Affordances

**UI.** MuJoCo passive viewer, used only on a machine with a display. Otherwise `render_replay` writes an mp4 with a camera inset and the score overlay.

| Affordance | Place | Wires to |
|------------|-------|----------|
| Replay mp4 | Local file after pod pull | S2, S3, S6 |
| Score and error overlay | Replay frame | S3 scorer |

**Non-UI.**

| Affordance | Kind | Wires to |
|------------|------|----------|
| `darts throw --target T20 --seed N` | CLI | S4, S5 |
| `darts train --config cfg.yaml` | CLI | S5, S8 |
| `darts eval --policy P --n 100` | CLI (JSON output, non-zero exit if target missed) | S5 |
| `darts sysid fit logs/` | CLI | S7 |
| `twin.yaml` | Config store | S1 |
| Run artifacts (`runs/<id>/`) | Directory with policy, metrics.json, replays | S5, S8 |

## Implementation decisions

- **State interface** (R4, ADR-0003): `target_in_base` (3D point on the board face, in the base frame), `board_normal_in_base` (unit vector), `joint_pos` (6, from encoders). It is a fixed dataclass with a unit-tested schema. The estimator outputs board pose, and a pure function turns that into the interface fields.
- **Throw action** (ADR-0004): one episode is one throw. The policy is effectively a contextual bandit and uses PPO via a standard library. The action space is small enough that CMA-ES is an equally valid fallback.
- **Actuators**: position servos with PD gains from `twin.yaml`, plus explicit velocity and torque clamps and a command-to-motion latency parameter. The release time is an actuation of the gripper jaw, and jaw open time is itself a twin parameter.
- **Camera**: 640×480, intrinsics in `twin.yaml`. Mounted on a mast rigidly attached to the base, offset to the side and raised so the arm never crosses the line of sight to the board.
- **Failure behaviour**: out-of-limit actions are clipped and flagged in `info`, not raised. A NaN or diverging sim aborts the episode, logs the seed, and counts as a miss in eval.
- **Determinism**: every random draw comes from a seeded generator, and eval takes a seed list.
- **Versioning**: `twin.yaml` carries `schema_version`. Migrations are deferred (Q9).
- **Dependencies**: MuJoCo, Gymnasium, Stable-Baselines3, NumPy, OpenCV (estimator) and imageio-ffmpeg, all permissively licensed and offline-capable. Menagerie SO-101 is Apache-2.0. See Q10.
- **Secrets**: the RunPod API key comes from the environment only. The runner never prints it, writes it to run artifacts, or commits it, and a test scans artifacts and logs for it.
- **Language and host**: Python, uv-managed, developed on WSL2, run on RunPod.

## Testing approach

Test the highest seams: the Gymnasium env (a throw gives a score and error) and the CLI. Check behaviour, not internals. Physics is tested by analytic cases, such as a ballistic arc with drag off matching the closed form, and a dart dropped on the board face sticking.

Acceptance numbers are statistical, so evals use fixed seed lists and report median and 90th-percentile tip error.

Pods must be torn down on every path. The runner uses the runpod-jobs dead-man's-switch pattern. A CI-style smoke test runs on the laptop with a tiny CPU config, so most logic is exercised without a pod.

## Assumed defaults

| ID | Assumed | Cost if wrong |
|----|---------|---------------|
| Q3 | Weld-or-bounce sticking, scored from tip contact point | Low. Only scoring edge cases change |
| Q4 | Simple drag plus restoring-torque flight model | Medium. A poor fit at 1.0 m would shift hits by centimetres, and V9 sysid absorbs it |
| Q5 | One `twin.yaml` is the only source of physical parameters | High if broken. Hard-coded numbers elsewhere would defeat the twin |
| Q13 | Targets: ≥90% of throws on board and median tip error ≤3 cm on state | High. V1 shows 1.0 m sits near the arm's limit (best miss 9 cm), so the ≤3 cm target may need a shorter range or may not be reachable at all. V3 baselines: a fixed throw panned at the target gets median 8.3 cm. V4 will tell |

## Open risks

- **Throw speed (measured in V1).** The servo velocity limit (4.5 rad/s) caps forward release speed near 3.2 m/s, which puts the board at 1.0 m with little headroom: best miss 3 cm at 0.9 m, 9 cm at 1.0 m, 16 cm at 1.1 m, 25 cm (a miss) at 1.2 m. Details in `docs/v1-feasibility.md`. A faster real servo supply voltage (12 V STS3215, about 7 rad/s) would extend this and is worth checking on hardware.
- **Release timing.** Gripper opening latency of tens of milliseconds moves the landing point by several centimetres. Latency is a twin parameter and is randomised in V5.
- **Actuator model fidelity.** The Menagerie model's servo behaviour may be too ideal. V9's fit against synthetic data shows the method works, but the real calibration waits for hardware.
- **Rendering on pods.** Headless EGL needs a GPU pod, and OSMesa is the CPU fallback. V6 confirms which works on the chosen template.
