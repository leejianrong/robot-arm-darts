# ADR-0004: A throw is one episode with a small parametrised action

- Status: Accepted
- Date: 2026-11-04
- Deciders: Jian (F5), Claude (action form, assumed)

## Context

A dart throw takes under a second, with no useful feedback after release. Per-step joint control would give a huge action space for a task that is almost open-loop.

## Decision

The policy emits one action per throw: about 8 numbers that define joint waypoints and velocity profile, plus a release time. The sim executes it through the actuators. Reward is the negative distance from the dart tip to the target, with a bonus for a board hit. PPO from Stable-Baselines3 is the default learner.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Per-step torque or position RL | Wastes samples on a task with no mid-flight feedback |
| Analytic trajectory plus inverse kinematics only | No learning, and it can't absorb unmodelled effects like release latency |
| CMA-ES or Bayesian optimisation | Kept as a fallback. It can't generalise across targets as cleanly as a conditioned policy |

## Consequences

Training is cheap and episodes are short. The action maps directly onto commands a real arm can execute, which helps the sim-to-real transfer. The cost is that the policy cannot correct itself during the throw, so release timing precision matters a lot.
