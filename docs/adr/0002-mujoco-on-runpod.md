# ADR-0002: MuJoCo, with all training and rendering on RunPod

- Status: Accepted
- Date: 2026-11-04
- Deciders: Jian (F2)

## Context

The laptop has little compute, and you plan to use RunPod GPUs for simulation, including CPU-bound MuJoCo. Throwing is a short, low-dimensional task, so raw simulation throughput matters less than reproducibility and cheap iteration.

## Decision

The simulator is MuJoCo (Apache-2.0). Training, evaluation and replay rendering run headless on RunPod. The laptop edits code, runs a tiny CPU smoke test, and views pulled mp4 files. Every pod job uses the teardown guarantee from the runpod-jobs skill. GPU-based MJX is optional and deferred.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Isaac Sim/Lab | Needs an RTX card, heavy, and its payoff is large-scale parallel RL we don't need for a one-shot throw |
| Genesis, ManiSkill | Newer, with a thinner ecosystem around the SO-101 and sysid |
| PyBullet | Largely legacy. Contact quality is weaker for a grasp-and-release |
| Local training | Laptop too weak, and the wait would slow iteration |

## Consequences

Rented compute means a billing risk, so teardown is a hard requirement. Headless rendering needs EGL (GPU pods) or OSMesa (CPU pods), and V6 settles which. There is no interactive viewer on pods, so debugging relies on replays.
