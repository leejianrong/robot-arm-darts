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

Narrowing run at 7.85 rad/s (the STS3250's no-load speed), same method, seed 1:

| Torque | Best miss | Arrival | Hits board |
|---|---|---|---|
| 4.5 N.m | 0.27 m | 40 deg | no |
| 4.9 N.m | 0.06 m | 29 deg | yes |
| 5.2 N.m | 0.04 m | 26 deg | yes |
| 5.5 N.m | 0.04 m | 39 deg | yes |
| 5.8 N.m | 0.02 m | 33 deg | yes |

The threshold is between 4.5 and 4.9 N.m at 7.85 rad/s. Margin is thin: 4.9 N.m (the STS3250's listed stall torque) only just reaches, from one seed, with flat torque that real servos do not deliver at speed.

Reading:
- Torque decides it. Between 4 and 6 N.m the board goes from out of reach to reachable; speed above 7 rad/s adds almost nothing.
- Requirement for 2.37 m: **at least 4.9 N.m (50 kg.cm) of delivered torque at about 7 to 8 rad/s (67 to 75 rpm); about 6 N.m (61 kg.cm) for margin**. The threshold lies between 4.5 and 4.9 N.m at 7.85 rad/s.
- The 6 N.m hits are rough: one cell's best throw is a 58 deg lob. A finer search and the base-throw map come after a servo is chosen.
- The sim uses a flat torque limit at every speed. Real servo torque falls as speed rises, so a real part needs more than 6 N.m of stall torque to deliver it at 7 rad/s.

## With torque that falls as speed rises (the realistic servo)

A DC servo's torque falls roughly linearly from its stall torque T0 at standstill to zero at its no-load speed w0. The sim now models this (`servo.no_load_speed_rad_s` in `twin.yaml`, 0 keeps the flat torque of the tables above; every arm joint gets the same curve). Same 2.37 m reach search, `JOB=reach` with `REACH_DERATE=1`, seed 1. Peak mechanical power per joint is T0 x w0 / 4.

| No-load speed w0 | Stall torque T0 | Peak power | Best miss | Hits board |
|---|---|---|---|---|
| 7.85 rad/s | 4.9 N.m | 9.6 W | none reaches | no |
| 7.85 rad/s | 6 N.m | 11.8 W | 1.69 m | no |
| 7.85 rad/s | 8 N.m | 15.7 W | 1.05 m | no |
| 7.85 rad/s | 10 N.m | 19.6 W | 0.64 m | no |
| 12 rad/s | 6 N.m | 18 W | 0.84 m | no |
| 12 rad/s | 8 N.m | 24 W | 0.17 m | edge of the scoring radius |
| 12 rad/s | 10 N.m | 30 W | 0.11 m | yes |
| 16 rad/s | 6 N.m | 24 W | 0.46 m | no |
| 16 rad/s | 8 N.m | 32 W | 0.03 m | yes |
| 16 rad/s | 10 N.m | 40 W | 0.01 m | yes |

Reading: both numbers matter. Hitting 2.37 m needs about **12 rad/s (115 rpm) or more with 8 to 10 N.m (82 to 102 kg.cm) of stall torque, or 16 rad/s with 8 N.m: roughly 25 to 30 W of peak power per joint.** The flat-torque result above (4.9 N.m is enough) was too optimistic. Even 10 N.m at 7.85 rad/s does not reach the board.

## Real servo candidates

Figures come from retailer listings, not datasheets; check them before they go in `twin.yaml`.

| Servo | No-load speed | Stall torque | Peak power | Verdict |
|---|---|---|---|---|
| STS3215 7.4 V (SO-101 stock) | 5.4 rad/s (twin uses 4.5) | about 1.9 N.m (twin: 2.94 from the Menagerie model) | about 2.6 W | far too weak |
| STS3215 12 V "C018" | 4.7 rad/s | 2.9 N.m | 3.4 W | too weak |
| ST3215-HS 12 V | 11.1 rad/s | 1.96 N.m | 5.4 W | fast but weak |
| STS3250 12 V "C002" | 7.85 rad/s | 4.9 N.m | 9.6 W | fails even at 10 N.m and this speed; about a third of the power needed |
| Dynamixel XM430-W350 | 4.8 rad/s | 4.8 N.m | 5.8 W | too slow and weak |

Nothing in the hobby smart-servo class listed here comes close. The need is about 25 to 30 W of peak power at 12 to 16 rad/s, which points at brushless actuators (quasi-direct-drive or planetary-geared BLDC modules) on the shoulder and elbow. Not yet researched: which real ones fit.

Corrections: `docs/v1-feasibility.md` once said a 12 V STS3215 reaches about 7 rad/s. It does not; the 12 V part is the high-torque variant. An earlier version of this page also named the HS part and then the STS3250 as candidates; the flat-torque sweeps that suggested them ignored torque loss with speed.

Conversions: rpm x 2 pi / 60 = rad/s; kg.cm x 0.0981 = N.m.

## Brushless actuator shortlist (2.37 m)

Need: stall (peak) torque 8 to 10 N.m and no-load speed 12 to 16 rad/s or more on the shoulder and elbow (see the derated sweep). Figures are from retailer and distributor listings and conflict in places; the official datasheets decide before anything is bought or set in `twin.yaml`. Peak power = peak torque x no-load speed / 4. Treating "peak torque" as the stall torque of the sim's straight-line curve is a guess; real drives hold torque flat up to a base speed, so the line is probably conservative.

| Actuator | Peak torque | No-load speed | Peak power | Weight | Listed price | Fit |
|---|---|---|---|---|---|---|
| CubeMars AK60-6 V3 (KV80) | 9 N.m | 320 rpm = 33.5 rad/s (at 24 V; 640 rpm quoted for 48 V) | about 75 W | 380 g (one distributor says 1.5 kg, probably packaged) | about $400 to $500 | meets the bar with 3x speed margin; smallest and cheapest |
| MyActuator RMD-X6-8 | 10 N.m (another listing: 8) | 310 rpm = 32 rad/s (rated speed; no-load higher) | about 80 W | 0.49 to 0.8 kg (listings conflict) | not found | meets the bar; weight unclear |
| CubeMars AK70-10 KV100 | 24.8 N.m | 240 rpm = 25 rad/s (24 V) | about 155 W | 521 g | about $400 to $500 | well above the bar; more weight and cost than needed |
| CubeMars AK80-9 KV100 | 18 N.m | 533 rpm = 56 rad/s | about 250 W | 485 g | about $470 to $570 | far above the bar |

Not searched: Unitree actuators, Dynamixel's larger X-series, and ODrive-based DIY builds.

Reading:
- The brushless class clears the requirement by a wide margin on speed; the AK60-6 and RMD-X6-8 also reach the 8 to 10 N.m stall torque with little to spare, so torque is the number to watch.
- Costs add up: two big joints is about $800 to $1,000 before a supply, CAN interface and wiring. They run on 24 to 48 V over CAN, not the 6 to 12 V serial bus of the SO-101 servos, so the electronics and the LeRobot interface change.
- Weight: 0.4 to 0.5 kg sits on the arm. The stock SO-101 links total about 0.5 kg moving mass, so the arm would roughly double in weight. The sim has not seen this yet; the 25 to 30 W estimate assumed the stock links, and more mass needs more torque.
- Which joints: shoulder_lift and elbow_flex do the swing. A shoulder actuator mounted at the base mostly adds no moving mass; an elbow actuator rides on the upper arm and does.

Next in the spike: model the extra link mass and re-run the 2.37 m search with an AK60-6 (9 N.m, 33.5 rad/s) on the shoulder and elbow only, and the stock servos elsewhere.

## Power-joint search with added actuator mass (2.37 m)

`twin.yaml` has a `power` section: bigger actuators on shoulder_lift and elbow_flex only (stock servo elsewhere), with the actuator's mass added to the shoulder body and the upper arm. Off by default (`torque_limit_nm: 0`). Same reach search, seed 1, `REACH_POWER_SETS` on the pod job. Sets are torque : no-load speed : shoulder mass : elbow mass.

| Case | Best throw | Miss | Release | Sticks in 54 aero and timing variants |
|---|---|---|---|---|
| AK60-6, no added mass (9 N.m, 33.5 rad/s) | 5.1 m/s, 42 deg, from 1.32 m | 1 mm | 177 deg off its path | 22% |
| AK60-6, 0.38 kg on shoulder and elbow | 5.0 m/s, 43 deg, from 1.31 m | 4 mm | 175 deg off its path | 20% |
| RMD-X6-8-like (10 N.m, 32.5 rad/s, 0.65 kg each) | 5.0 m/s, 29 deg, from 1.88 m | 5 mm | 13 deg off | 24% |
| AK70-10 (24.8 N.m, 25.1 rad/s, 0.52 kg each) | 9.4 m/s, 2 deg, from 1.88 m | 0 mm | 17 deg off | 56%, median miss 3 cm |

Reading:
- Every case finds a throw that hits the centre, so reach is not the limit with this class of actuator, and the added 0.4 to 0.65 kg did not stop it.
- None of the throws is reliable. The search returns the single luckiest throw (a 1 mm miss), spins the dart at 54 to 59 rad/s (earlier 0.5 m throws spun at 6 to 18), and the AK60 throws release the dart tail-first. Across the aero guesses and +/-10 ms of release timing they stick only 20 to 56% of the time. This is the same knife-edge pattern as the V4 tumbling result; a reachable board is not yet a throwable one.
- The AK70's 9.4 m/s release is above the 6 m/s that CLAUDE.md treats as a likely artifact; do not trust it.
- The earlier flat-torque and derated sweeps used the same objective and were not checked for robustness either. Their "hits" show reach, not reliable throws.

Next: make the search objective robust (average the cost over release-time jitter and aero variants, and penalise tail-first or very fast spin releases) and re-run these four cases. Until then no actuator is confirmed.

## Decision (2026-11-07)

- `twin.yaml` stays at the working setup: board 0.5 m, stock servos, `power` off. It is the only setup with a robust throw (sticks 100% across the aero guesses, base-throw map in `docs/baselines/basemap.json`).
- The planned 2.37 m actuator is the CubeMars AK60-6 (9 N.m, 33.5 rad/s) on shoulder_lift and elbow_flex, stock servos elsewhere. It is a design target only: no 2.37 m throw has been shown reliable (20 to 56% sticks across variants), and the listing figures are unchecked against datasheets.
- Switching `twin.yaml` to 2.37 m waits for a robust search (average the cost over release jitter and aero variants, penalise tail-first and very fast spin releases) that finds a throw sticking in at least 80% of variants. Tracked as a Pandan card.

## Sanity check against human throwers

Sources were thin. Joint-speed numbers for dart throwers were not in the search results (the full texts of Nasu et al. 2014, PLoS ONE, https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6797117/ and the JHSE joint-kinematics paper are the places to look).

- Release speed: one page in the search results (not identified, treat as unverified) gives about 5.5 m/s for experienced overhand throwers. The ballistic table above needs 4.8 to 5.4 m/s at a 20 to 30 deg release, so the target speed matches a human throw.
- Joint speed (arithmetic, not a measurement): 5.5 m/s at the fingertip with a 0.45 to 0.6 m reach is 9 to 12 rad/s, or 525 to 700 deg/s. The 12 to 16 rad/s the sim needs is the same order as that, a bit higher because the sim's throw is a planar swing with no wrist snap.
- Power (arithmetic from the model): the arm's moving links weigh about 0.5 kg. Moving them at an average of about 2.5 m/s is about 1.6 J, in about 0.15 s: roughly 10 W average and 25 to 30 W at the peak, which matches the sweep. A human forearm and hand (about 1.3 kg, general anatomy figure, not from the sources) reaching the same speeds needs about 60 W, which muscle supplies easily; the dart itself (10 g at 5.5 m/s) carries only 0.15 J.

Conclusion: the numbers make sense. Speed matches a human throw, and the power is small for muscle but several times what a 3 W hobby servo can deliver. The gap is the actuators, not the physics.

## Open items

- Check the shortlist against official datasheets (the listings conflict) and fit the real torque-speed curve instead of the straight line.
- Mass and inertia of the bigger actuators (the sim still uses the stock SO-101 links), joint backlash, and which joints really need the big actuator (probably shoulder and elbow; the wrist and gripper may stay small).
- Repeat the 12 rad/s, 8 N.m edge with more seeds; one seed decides it.
- Drag, grip creep (the dart slips out after 0.45 s) and the arrival margin are guesses.
- Decide the arm: SO-101 with bigger actuators on two joints, or a different arm.

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
