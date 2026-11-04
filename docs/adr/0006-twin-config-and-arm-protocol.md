# ADR-0006: One twin.yaml and one Arm protocol for sim and hardware

- Status: Accepted
- Date: 2026-11-04
- Deciders: Claude (assumed Q5, Q6), Jian's digital-twin goal

## Context

The point of the project is to tune parameters to match a real arm and deploy. If physical numbers are scattered through code, or the sim and the real arm are driven through different interfaces, that fails.

## Decision

- `twin.yaml` is the only source of calibratable physical parameters: servo gains, velocity and torque limits, command latency, jaw open time, masses, friction, dart aero coefficients, and camera intrinsics and pose. It has a `schema_version`.
- The `Arm` protocol exposes `set_targets`, `read_state` and `open_gripper`. `SimArm` implements it now. A `LeRobotArm` backend is a stub, and the real driver will be LeRobot.
- A sysid fitter minimises the distance between simulated and logged joint trajectories to estimate twin parameters.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Parameters as constants in code | Every calibration would be a code change |
| A separate sim-only control API | Would force a rewrite at deployment |

## Consequences

Calibration becomes editing a file or running a fit. The policy and env never touch hardware specifics. The cost is discipline: a hard-coded number anywhere else breaks the twin, so a test greps for parameters that duplicate `twin.yaml` keys.
