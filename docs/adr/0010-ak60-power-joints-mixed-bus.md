# ADR-0010: AK60-6 on shoulder and elbow, SO-101 everywhere else, one mixed bus

- Status: Accepted
- Date: 2026-11-09
- Deciders: Jian

## Context

Derated sweeps need about 25 to 30 W of peak power per swing joint (8 to 10 N.m at 12 to 16 rad/s); hobby smart servos give 3 to 10 W. The CubeMars AK60-6 V3 (KV80) lists 3 N.m rated, 9 N.m peak, 320 rpm (33.5 rad/s) no-load at 24 V, 380 g, 6:1 gearing and 9 arcmin backlash on its [spec table](https://img.cubemars.com/products/cubemars-product-parameter/AK60-6-V3.0-KV80.pdf). The table's columns are unlabelled in the copy read, so peak torque and no-load speed are inferred from column order.

## Decision

- Keep the SO-101 links and the ADR-0001 target. Swap shoulder_lift and elbow_flex for AK60-6 V3 (the twin's `power` section); pan, wrist and gripper stay on the STS3215.
- The new joints talk CAN at 24 V; the rest stay on the serial bus. `LeRobotArm` therefore needs a mixed backend, written when hardware exists (DART-39, deferred).
- `power` takes datasheet numbers after a check against the official PDF (DART-38): peak against rated torque, a torque-speed curve with a constant-torque region instead of the straight line, backlash, and the actuator masses.

## Alternatives considered

| Option | Why not |
|--------|---------|
| MyActuator RMD-X6 | Comparable class, but no official V3 datasheet found; listings conflict on torque and weight |
| CubeMars AK70-10 | Torque well above need, more weight; the robust search at 5.9 m/s also stuck only 56% |
| A custom arm | Gives the twin nothing to compare with and drops ADR-0001 |

## Consequences

Peak torque is a transient (rated is 3 N.m), fine for a 0.2 s swing but unconfirmed until a bench test. Roughly 0.4 kg per actuator doubles the arm's moving mass, already modelled (`shoulder_mass_kg`, `elbow_mass_kg`). CAN and 24 V mean new electronics and a new driver, so the arm cannot be a drop-in SO-101.
