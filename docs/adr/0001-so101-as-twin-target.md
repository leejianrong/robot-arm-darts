# ADR-0001: The SO-101 is the real arm the sim twins

- Status: Accepted
- Date: 2026-11-04
- Deciders: Jian (F1)

## Context

The goal is a digital twin of an arm you will buy later, on a limited budget. The arm has to have a gripper that can hold and release a dart, an existing MuJoCo model, and a community that publishes its parameters.

## Decision

The twin target is the SO-101 (five joints plus a two-jaw gripper). The sim starts from the MuJoCo Menagerie `robotstudio_so101` model and overlays actuator and physical parameters from `twin.yaml`.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Franka Panda, UR5e | Can throw harder, but cost 10–100 times more, so the twin would not match the arm you are likely to buy |
| WidowX or Piper class arms | Mid-priced, with fewer ready models and less LeRobot-style tooling |
| An arm-agnostic sim | No concrete limits to calibrate against, so R1 could not be tested |

## Consequences

Cheap and well documented, with a ready MJCF. The cost is limited power: servo speed caps the release velocity, and a 1.5 m throw proved infeasible in V1; the range is now 0.5 m (see PLAN risk and docs/v1-feasibility.md). The model's servo behaviour is idealised until it is fitted to hardware.
