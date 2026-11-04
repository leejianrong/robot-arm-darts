# ADR-0007: The camera sits on a mast from the base frame and must never be occluded

- Status: Accepted
- Date: 2026-11-04
- Deciders: Jian (F6)

## Context

The arm swings through a large volume while throwing. A wrist camera would move and lose the board. You also ruled out any camera that moves with the arm.

## Decision

The camera is rigidly fixed in the base frame, on a mast raised and offset to the side, looking at the board. Its pose and intrinsics are in `twin.yaml`. A segmentation render checks that the board's pixels stay visible through the whole throw, and that check is an acceptance test.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Wrist or gripper camera | Moves with the arm, loses sight of the board mid-throw (ruled out) |
| Camera fixed in the world, independent of the arm | Breaks the digital-twin idea of one rigid robot-plus-camera assembly |

## Consequences

The estimator works in a constant camera frame, so the camera-to-base transform is calibrated once. The real arm needs a physical mast with the same geometry. If a throw ever occludes the camera, the test fails, and the camera pose or the throw has to change.
