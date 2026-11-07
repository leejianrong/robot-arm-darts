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

## Joint speed needed (first estimate)

Release speed scales about linearly with joint speed (tip speed = rate x reach), so with 2.8 m/s at 4.5 rad/s:

| Joint speed | Release speed (linear estimate) |
|---|---|
| 4.5 rad/s | 2.8 m/s |
| 7 rad/s | 4.4 m/s |
| 9 rad/s | 5.6 m/s |
| 11 rad/s | 6.8 m/s |

So the target is roughly 8 to 9 rad/s. This is optimistic: it ignores torque, acceleration time and the 0.45 s limit on how long the grip holds the dart. The simulated search (below) replaces the estimate.

## Real servo candidates

Figures are from retailer listings and need checking against the Feetech datasheet before they go in `twin.yaml`.

| Servo | Speed | Stall torque | Note |
|---|---|---|---|
| STS3215 7.4 V (SO-101 stock) | 0.192 s / 60 deg = 52 rpm = 5.4 rad/s no-load (we use 4.5) | about 19.5 kg.cm = 1.9 N.m (twin uses 2.94 N.m from the Menagerie model) | what the SO-101 ships with |
| STS3215 12 V "C018", 1/345 gear | 0.222 s / 60 deg = 45 rpm = 4.7 rad/s | 30 kg.cm = 2.9 N.m | more torque, **not faster** |
| ST3215-HS 12 V "106 RPM" | 106 rpm = 11.1 rad/s | 20 kg.cm = 1.96 N.m | same body, lower gear ratio; the likely drop-in for speed |

Correction: `docs/v1-feasibility.md` once said a 12 V STS3215 reaches about 7 rad/s. The listings say it does not; the faster part is the HS variant.

Conversions: rpm x 2 pi / 60 = rad/s; kg.cm x 0.0981 = N.m. The HS part trades torque for speed (1.96 against 2.94 N.m), so the twin must lower `torque_limit_nm` with it.

## Open items

- Speed sweep at 2.37 m (below) gives the minimum joint speed the sim needs, with torque at 2.94 N.m. Follow with the HS torque (1.96 N.m).
- Drag, grip creep (the dart slips out after 0.45 s) and the arrival margin are guesses; the HS result is only as good as they are.
- Voltage: the HS part needs a 12 V supply, which the stock 7.4 V SO-101 kit does not have.

Reproduce the table:

```python
import math
g, dx, dz = 9.81, 2.27, -0.17
for deg in (10, 20, 30, 45):
    a = math.radians(deg)
    v = math.sqrt(g * dx**2 / (2 * math.cos(a) ** 2 * (dx * math.tan(a) - dz)))
    t = dx / (v * math.cos(a))
    print(deg, round(v, 2), round(t, 2), round(math.degrees(math.atan2(g * t - v * math.sin(a), v * math.cos(a)))))
```
