# V1 feasibility: can the SO-101 throw a 10 g dart onto the board?

Run on 2026-11-04 with `darts throw --scripted --seed 1 --maxiter 60 --popsize 20` at each board distance (about 8,000 simulated throws per row, differential evolution over a planar three-joint flick and the release time). A "hit" is a throw that crosses the board plane within the 170 mm scoring radius of the board centre (1.73 m above the floor), with the dart held by friction the whole time until the jaw opens and never touching anything but the jaw pads and the floor.

Twin: servo velocity limit 4.5 rad/s, torque limit 2.94 N·m, 10 g dart, pad friction 1.0, arm on a 1.2 m stand.

| Board distance | Best miss from centre | Release speed | Release angle | Hits board |
|---|---|---|---|---|
| 0.9 m | 0.03 m | 3.1 m/s | 52° | yes |
| 1.0 m | 0.09 m | 3.1 m/s | 48° | yes |
| 1.1 m | 0.16 m | 3.1 m/s | 49° | marginal |
| 1.2 m | 0.25 m | 3.2 m/s | 46° | **no** |

Findings

- Forward release speed tops out near **3.2 m/s**. It is capped by the servo velocity limit: each joint's tip speed is angular rate times reach, and the three add up to about 3.2 m/s only when everything lines up. Faster throws (up to 4.8 m/s) exist, but they all point downward.
- Four independent seeds converged on the same throw, which supports reading this as the physical optimum and not a search failure.
- **1.5 m and 1.2 m are out of reach.** 1.0 m works but with almost no headroom: the best throw misses the centre by 9 cm, so hitting a specific segment (the plan's ≤3 cm median target, Q13) is not demonstrated. Q13 may need a shorter range or a faster servo supply (12 V STS3215 is about 7 rad/s).

Sanity checks that shaped the result

- An early run reported hits at 21 to 92 m/s release speed. Those were solver artifacts or the arm batting the dart. Any dart contact outside the jaw pads and floor now invalidates a throw.
- Releases are confirmed only after several steps without pad contact, because contact flickers while the jaw is still pushing the dart.
- Floor contact ends the flight and does not count as a collision.

Assumptions that move the result: servo speed (datasheet 4.71 rad/s, measure on hardware), pad friction, and contact settings tuned in code (ADR-0008). A real dart, real pads and a real stand will all shift this.
