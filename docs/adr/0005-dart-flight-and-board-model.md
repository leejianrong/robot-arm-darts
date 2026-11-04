# ADR-0005: Dart flight uses a simple aero model, and the board sticks by geometry

- Status: Accepted
- Date: 2026-11-04
- Deciders: Jian (F3 realism), Claude (mechanism)

## Context

You asked for realism with a 10 g dart at about 1.5 m (later 1.0 m after V1). MuJoCo has no aerodynamics and no embedding in cork. A full simulation of either would cost more than it gives, but the dart must fly nose-first and score correctly.

## Decision

- **Flight:** each step applies a quadratic drag force on the dart body and a restoring torque that aligns the dart axis to its velocity, standing in for the fins. Coefficients live in `twin.yaml`.
- **Board:** a plane with disc and ring geometry for scoring. When the tip touches the face inside the board, and the speed and angle are within thresholds, a weld constraint freezes the dart. Otherwise it bounces. The score comes from the tip contact point.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Ideal ballistic body, no aero | Darts would tumble and miss real behaviour at a few metres per second |
| CFD or detailed fin geometry | Large cost for a few millimetres of accuracy |
| Soft-body board penetration | Expensive, unstable, and irrelevant to the score |

## Consequences

The model is cheap and tunable, and a real dart's flight can be fitted into the same coefficients. It will not capture dart wobble or board-specific bounce-outs. If sim and real flights disagree, the coefficients are the first thing sysid adjusts.
