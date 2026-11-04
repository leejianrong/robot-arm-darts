# ADR-0008: The dart is held by jaw friction and released by opening the jaws

- Status: Accepted
- Date: 2026-11-04
- Deciders: Jian

## Context

The first V1 build glued the dart to the gripper with a rigid weld until the jaw angle passed a threshold. That has no slip, no friction and no release dynamics, so it hides exactly what sets a real dart's launch speed and direction. You asked for slip, friction and a release like a human's.

## Decision

The dart is a free body held by pad friction at the SO-101 fingertips, with the barrel along the finger direction and the tip forward. It leaves when the jaw opens and contact with the pads ends. Pad friction is a twin parameter. The jaw command squeezes against the dart, limited by the servo torque limit. The contact solver settings (`impratio`, pad `solref`) are fixed in code, because the Menagerie defaults let a pinched dart creep out in about half a second.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Rigid weld until a jaw-angle threshold | No slip or release dynamics, so launch error would be invisible until real hardware |
| Teleport the dart at release | Same, and it ignores jaw timing |

## Consequences

Release speed, angle and any slip now come from the simulation, and V5 can randomise pad friction. Contact numerics are delicate: tiny pad geometry and a 7 mm barrel needed tuning, and the 7 mm dart diameter matches the SO-101 closed jaw gap. A real dart barrel and pads may need different values. Pad friction and the real jaw gap must be measured on hardware.
