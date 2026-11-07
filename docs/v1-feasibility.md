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
- **1.5 m and 1.2 m are out of reach.** 1.0 m works but with almost no headroom: the best throw misses the centre by 9 cm, so hitting a specific segment (the plan's ≤3 cm median target, Q13) is not demonstrated. Q13 may need a shorter range or a faster servo (the 12 V STS3215 is not faster: it is the high-torque variant at about 4.7 rad/s; see `docs/real-darts-range.md`).

Sanity checks that shaped the result

- An early run reported hits at 21 to 92 m/s release speed. Those were solver artifacts or the arm batting the dart. Any dart contact outside the jaw pads and floor now invalidates a throw.
- Releases are confirmed only after several steps without pad contact, because contact flickers while the jaw is still pushing the dart.
- Floor contact ends the flight and does not count as a collision.

Assumptions that move the result: servo speed (datasheet 4.71 rad/s, measure on hardware), pad friction, and contact settings tuned in code (ADR-0008). A real dart, real pads and a real stand will all shift this.

## Update (V4 follow-up): the 1.0 m result needs a tumbling dart

The release attitude was not recorded in V1 or V2. Measuring it (`release_misalign_rad`, `release_spin_rad_s`) showed that the best throws release the dart about **95° off its direction of travel, spinning at about 14 rad/s**. The dart tumbles end over end for the whole flight, and whether it sticks depends on which way it happens to point when it arrives: moving the release time by 1 ms changed the arrival angle from 18° to 151°. A real throw releases the dart nose-forward. With the dart held along the fingers, the arm's whip motion moves the fingertip sideways to the fingers, so a clean release needs a different motion.

The search first penalised a tumbling release and found nothing at 1.0 m. So 1.0 m was **not** shown to be reachable with a believable throw.

## Update (cross grip): the reach at the 4.5 rad/s limit is about 0.5 m

The dart is now held across the fingers with the wrist rolled 90° (`GRIP_ROLL_RAD`, `_DART_IN_GRIP` in `sim.py`), so its axis lies in the swing plane and leaves along its direction of travel (a test checks this). Findings, from searches of 4,000 to 12,000 throws per distance:

- **Spin cannot be avoided.** A hand that moves fast also rotates (a hand rotating at zero speed moves at 0.5 m/s). The dart leaves spinning at 6 to 18 rad/s, so the search judges the arrival angle, with 0.7 rad as its margin inside the 0.9 rad stick limit, not the release.
- **Speed is the limit.** The best usable release is about 2.8 m/s. Best misses were 0.38 m at 1.0 m, 0.25 m at 0.9 m, 0.23 m at 0.8 m and 0.18 m at 0.7 m (not on the board); at 0.5 m a dart sticks 15 cm below the centre.
- **The 0.5 m throw is fairly robust.** It sticks in 83% of 54 variants (aero guesses x release time within 10 ms), median miss 15 cm. It sits at the lower rim because a higher release angle makes the dart arrive too slanted.
- **The grip is marginal.** The jaws pinch at their tip edges, the dart creeps out after about 0.45 s of swinging, and the search is limited to releases before that.
- **The solver warnings were the post-contact replay.** MuJoCo prints "unstable" while the bounce after a hit plays out (a thin 10 g capsule), and resets itself. That only ran for replays after the result was recorded, so it never touched a score. It now runs only when rendering. Throws that go unstable before the result are flagged `diverged`, including when MuJoCo resets silently.

## Update (stand raised to 1.4 m, shoulder height of an average adult)

The V1 tables above were measured on a 1.2 m stand. `twin.yaml` now mounts the arm at 1.4 m. The board stays at 1.73 m, so the climb from the base is 0.33 m instead of 0.53 m and the dart arrives flatter.

- The unchanged hand throw sticks on 30 of 30 held-out seeds, median miss 7.6 cm, p90 16 cm. On the 1.2 m stand it was 84% on board with an 18 cm median.
- The nominal throw lands 5 cm from the centre, and sticks at release-time offsets of up to 10 ms either way (arrival 0.56 to 0.80 rad).
- Not redone on the new stand: the reach search per board distance, `darts robust` across the aero guesses, and the per-target base-throw map. The 0.5 m board distance was chosen for the old height and may now allow a longer range.

Base-throw map on the 1.4 m stand (CPU pod, 80 targets, 2 rounds): 73 of 80 targets reach within 6 cm, against 11 of 80 on the 1.2 m stand. A quadratic map left the top rim (z above +11 cm) unreachable (89% stuck); a cubic map sticks 94 to 99% across three sets of 100 seeds with a 2.4 to 2.8 cm median and a 6.7 cm p90 on the best set (`docs/baselines/basemap.json`; degree 4 overfits at 87%). The degree was chosen on seeds 10000 to 10099, then checked on 20000 and 30000.

Robustness of the cubic map (54 variants per target: 3 fin torque x 3 spin damping x 2 drag x release time within 10 ms): the dart sticks 100% at the centre and at four points 10 cm out, with a median miss from the target of 0.4 to 1.0 cm at the centre, left and right, 1.9 cm at the bottom and 4.1 cm at the top (worst 6.1 cm). The aero guesses do not break the throw.

Upper rim limit: 10 of 300 fresh seeds miss, all at z +8 to +12 cm. The per-target search misses by 6 to 10 cm at z +11 cm and above too, because every best throw arrives at exactly 40 degrees, the 0.7 rad margin inside the 0.9 rad stick limit. Options if the top rim matters: widen that margin to about 0.85 rad (the stick limit is a guess), or raise the stand to about 1.5 m. Left as is: about 97% of the board works.
