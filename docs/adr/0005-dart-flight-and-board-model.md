# ADR-0005: Dart flight uses a simple aero model, and the board sticks by geometry

- Status: Accepted
- Date: 2026-11-04
- Deciders: Jian (F3 realism), Claude (mechanism)

## Context

You asked for realism with a 10 g dart at about 1.5 m (later 1.0 m after V1). MuJoCo has no aerodynamics and no embedding in cork. A full simulation of either would cost more than it gives, but the dart must fly nose-first and score correctly.

## Decision

- **Flight:** each step applies a quadratic drag force on the dart body and a restoring torque that aligns the dart axis to its velocity, standing in for the fins. Coefficients live in `twin.yaml`.
- **Board:** a thin collidable disc of the scoring radius, with regulation rings scored in pure Python (`board.py`). On first contact the dart sticks if its speed along the board normal and its angle to the normal are within the `twin.yaml` thresholds, else it counts as a bounce. Either way the throw ends at first contact, so a stuck dart needs no weld. The score comes from the contact point.
- **Unmeasured:** the stick thresholds and the aero coefficients are guesses, and the 2 m/s stick speed in particular decides whether a 3 m/s throw can score at all.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Ideal ballistic body, no aero | Darts would tumble and miss real behaviour at a few metres per second |
| CFD or detailed fin geometry | Large cost for a few millimetres of accuracy |
| Soft-body board penetration | Expensive, unstable, and irrelevant to the score |

## Consequences

The model is cheap and tunable, and a real dart's flight can be fitted into the same coefficients. It will not capture dart wobble or board-specific bounce-outs. If sim and real flights disagree, the coefficients are the first thing sysid adjusts.
