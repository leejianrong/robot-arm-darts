# Real darts range (2.37 m): the maths and the numbers

Why this exists: the twin throws at a board 0.5 m away because the servo speed limit reaches no further. A real darts board is 2.37 m from the throw line. This page keeps the calculations so nobody redoes them. Pandan card DART-33.

## Setup numbers (all from `twin.yaml` or the regulation)

| Quantity | Value |
|---|---|
| Throw line to board face | 2.37 m (regulation) |
| Board centre height | 1.73 m |
| Release point (measured on the 0.5 m throw) | about 1.9 m high, 0.1 m in front of the base axis |
| Horizontal flight dx | 2.37 - 0.1 = 2.27 m |
| Height change dz | 1.73 - 1.9 = -0.17 m |
| Gravity g | 9.81 m/s^2 |
| Arrival-angle margin the search keeps | 0.7 rad (40 deg) of the 0.9 rad stick limit (guesses, ADR-0005) |
| Joint speed limit in the twin now | 4.5 rad/s (datasheet 4.71 rad/s = 0.222 s per 60 deg, minus a buffer) |
| Release speed that gives | about 2.5 to 2.8 m/s (measured) |

## Release speed needed, no drag

Ballistic flight from release at angle a above horizontal and speed v:

    dz = dx tan(a) - g dx^2 / (2 v^2 cos^2(a))
    v  = sqrt( g dx^2 / (2 cos^2(a) (dx tan(a) - dz)) )
    flight time t = dx / (v cos(a))
    arrival angle below horizontal = atan( (g t - v sin(a)) / (v cos(a)) )

| Release angle | Speed v | Flight time | Arrival angle |
|---|---|---|---|
| 10 deg | 6.8 m/s | 0.34 s | 18 deg down |
| 20 deg | 5.4 m/s | 0.45 s | 27 deg down |
| 30 deg | 4.8 m/s | 0.55 s | 36 deg down |
| 45 deg | 4.6 m/s | 0.71 s | 49 deg down |

Reading: about 4.8 to 5.4 m/s at a 20 to 30 deg release, which arrives within the 0.7 rad margin (the dart flies point-first along its path, so a steeper arc arrives steeper). Real drag costs a few percent more. The arm now gives 2.8 m/s, so it needs about 1.8x the speed.

## What the simulation says the servo must do (measured)

First guess, from speed alone: release speed scales with joint speed (tip speed = rate x reach), so 2.8 m/s at 4.5 rad/s suggests about 8 to 9 rad/s. **That guess was wrong.** Throwing the 0.5 m throw with the speed limit raised from 4.5 to 14 rad/s at the stock torque (2.94 N.m) changes the release speed from 2.49 to 2.42 m/s. The arm is torque-limited, not speed-limited. Raising torque at fixed speed does help (9 rad/s: 6 N.m gives 6.0 m/s, untuned).

Scripted reach search at 2.37 m (differential evolution over a planar three-joint throw, about 10,800 throws per cell, seed 1, board stays at 2.37 m, 1.4 m stand, run on a CPU pod, `JOB=reach`). "Hits" means the dart lands inside the 17 cm scoring radius and sticks; miss is from the board centre.

| Speed limit | Torque limit | Best miss | Arrival | Hits board |
|---|---|---|---|---|
| 7 rad/s | 2.94 N.m | none reaches | | no |
| 7 rad/s | 4 N.m | 0.76 m | 40 deg | no |
| 7 rad/s | 6 N.m | 0.06 m | 38 deg | yes |
| 7 rad/s | 8 N.m | 0.05 m | 34 deg | yes |
| 9 rad/s | 2.94 N.m | none reaches | | no |
| 9 rad/s | 4 N.m | 0.67 m | 41 deg | no |
| 9 rad/s | 6 N.m | 0.07 m | 40 deg | yes |
| 9 rad/s | 8 N.m | 0.06 m | 9 deg | yes |
| 11 rad/s | 2.94 N.m | none reaches | | no |
| 11 rad/s | 4 N.m | 0.67 m | 40 deg | no |
| 11 rad/s | 6 N.m | 0.07 m | 33 deg | yes |
| 11 rad/s | 8 N.m | 0.01 m | 23 deg | yes |

Reading:
- Torque decides it. Between 4 and 6 N.m the board goes from out of reach to reachable; speed above 7 rad/s adds almost nothing.
- Requirement for 2.37 m: **about 6 N.m (61 kg.cm) of torque and about 7 rad/s (67 rpm)**. The threshold lies between 4 and 6 N.m and has not been narrowed.
- The 6 N.m hits are rough: one cell's best throw is a 58 deg lob. A finer search and the base-throw map come after a servo is chosen.
- The sim uses a flat torque limit at every speed. Real servo torque falls as speed rises, so a real part needs more than 6 N.m of stall torque to deliver it at 7 rad/s.

## Real servo candidates

Figures come from retailer listings, not datasheets; check them before they go in `twin.yaml`.

| Servo | No-load speed | Stall torque | Verdict |
|---|---|---|---|
| STS3215 7.4 V (SO-101 stock) | 0.192 s / 60 deg = 52 rpm = 5.4 rad/s (twin uses 4.5) | about 19.5 kg.cm = 1.9 N.m (twin: 2.94 from the Menagerie model) | too weak |
| STS3215 12 V "C018", 1/345 gear | 0.222 s / 60 deg = 45 rpm = 4.7 rad/s | 30 kg.cm = 2.9 N.m | not faster, same torque class: too weak |
| ST3215-HS 12 V "106 RPM" | 106 rpm = 11.1 rad/s | 20 kg.cm = 1.96 N.m | faster but weaker: does not help |
| STS3250 12 V "C002", 1/345 gear | 0.133 s / 60 deg = 75 rpm = 7.85 rad/s | 50 kg.cm = 4.9 N.m | speed fits; torque sits between the 4 N.m that fails and the 6 N.m that works: borderline |
| Dynamixel XM430-W350 | 46 rpm = 4.8 rad/s | 4.8 N.m (single reseller) | borderline torque, slow |

Corrections: `docs/v1-feasibility.md` once said a 12 V STS3215 reaches about 7 rad/s. It does not; the 12 V part is the high-torque variant. The first version of this page also named the HS part as the likely drop-in; the sweep shows speed is not what is missing.

Conversions: rpm x 2 pi / 60 = rad/s; kg.cm x 0.0981 = N.m.

## Open items

- Narrow the torque threshold: run 4.5, 5 and 5.5 N.m at 7 to 8 rad/s, and with the STS3250's own numbers (4.9 N.m, 7.85 rad/s).
- Model torque falling with speed (servo torque-speed curve), mass of the bigger servos (the STS3250 is heavier and larger than the STS3215, so the arm links and inertia change), and joint gear backlash.
- Drag, grip creep (the dart slips out after 0.45 s) and the arrival margin are guesses.
- Voltage: 12 V parts need a 12 V supply, which the stock 7.4 V SO-101 kit does not have.
- Decide the arm: SO-101 with bigger servos on the shoulder and elbow (the joints that do most of the work), or a different arm.

Reproduce the table:

```python
import math

g, dx, dz = 9.81, 2.27, -0.17
for deg in (10, 20, 30, 45):
    a = math.radians(deg)
    v = math.sqrt(g * dx**2 / (2 * math.cos(a) ** 2 * (dx * math.tan(a) - dz)))
    t = dx / (v * math.cos(a))
    print(
        deg,
        round(v, 2),
        round(t, 2),
        round(math.degrees(math.atan2(g * t - v * math.sin(a), v * math.cos(a)))),
    )
```
