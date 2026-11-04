# ADR-0003: Perception and control meet at a fixed state interface

- Status: Accepted
- Date: 2026-11-04
- Deciders: Jian (F5)

## Context

You want the pipeline to run camera, then state estimate, then agent. Training the policy from pixels would need far more compute and make sim-to-real harder to diagnose. The camera is in this milestone, but it comes after the policy works.

## Decision

The policy consumes only a fixed state dataclass: `target_in_base`, `board_normal_in_base` and `joint_pos`. Perfect state fills it first. An estimator later fills it from a rendered image. The policy never sees pixels. Training noise shaped like the estimator's measured error is added before the estimator exists, then replaced by real estimator output.

## Alternatives considered

| Option | Why not |
|--------|---------|
| End-to-end pixel policy | Expensive, hard to debug, and a bigger sim-to-real gap |
| Estimator and policy trained jointly | Couples two things that should be swappable |

## Consequences

The estimator can be improved or replaced (including by a real camera pipeline) without retraining the policy, as long as the error distribution stays within what the policy was trained on. The cost is that the estimator's errors are a separate failure source, so V7 measures them directly.
