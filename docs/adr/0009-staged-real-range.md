# ADR-0009: Work up to the 2.37 m throw in stages, gated in simulation

- Status: Accepted
- Date: 2026-11-09
- Deciders: Jian

## Context

A regulation throw is 2.37 m (steel tip, 7 ft 9¼ in) from the board face. The twin uses 0.5 m because stock servos reach no further. A 2.37 m throw with the AK60-6 power joints hits the centre but sticks in only 44 to 57% of variants (`docs/real-darts-range.md`, DART-34), so the setup cannot move there yet. The darts rules limit where the feet go, not the body, so a player may lean over the line. Nobody is buying hardware for the foreseeable future, so everything gates on simulation.

## Decision

1. **The base sits at the throw line.** `board.distance_m` is base axis to board and stays the 2.37 m target. The hand may reach up to 0.4 m ahead of the base axis at release, the lean of a human thrower (no source reports lean; the measured release velocity implies about 0.7 m in front of the line, so 0.4 m is conservative; the ladder also reports 0.2 m). The searches have released only 0.1 to 0.3 m ahead so far.
2. **Distance ladder.** Search with the AK60-6 power joints at 0.5, 1.0, 1.4, 1.8, 2.1 and 2.37 m (CPU pod, about $1). The farthest rung with at least 80% sticks in the 54 `darts robust` variants sets the working distance. `twin.yaml` moves there, with baselines redone. 2.37 m stays the goal until a throw passes there.
3. **Human sanity bands.** Every ladder row is flagged against what human players do (`docs/real-darts-range.md`): release speed 4.5 to 7 m/s, release angle 10 to 25 degrees (measured about 16), hand no further than the lean past the base. A result outside the bands is treated as a solver artifact until shown otherwise.
4. **No purchase gate.** Hardware is out of scope. When it comes back in scope, buy one AK60-6 first and bench-test its torque-speed curve and backlash before the second.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Hold out for a robust 2.37 m throw before changing anything | DART-34 suggests the knife-edge is structural; the twin would stay at 0.5 m indefinitely |
| Measure 2.37 m from the hand strictly | Ignores the rules as written and keeps the hardest case |
| Buy both actuators now | Out of scope, and a robust throw is not shown |

## Consequences

The working distance is a measured result, not a promise. If no rung beyond 1.0 m passes, the answer is a grip or wrist change (DART-37) before more distance. Lean is an assumption: a player who leans less, or a venue that disagrees, moves the ladder.
