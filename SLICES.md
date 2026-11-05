# Robot Arm Darts: Slices

Vertical increments. Each ends in something you can demonstrate. V1 confronts the riskiest unknown: whether the SO-101's actuators can throw a 10 g dart 1.5 m at all.

All runs of V3 onward execute on RunPod (ADR-0002). V1 and V2 are small enough for the laptop.

## V1: Can it throw? (feasibility)

**Delivers:** R1, R2 (partial), R0 (feasibility)

**Build plan**

1. Load the Menagerie SO-101 on a shoulder-height stand (1.4 m) (twin `mount.height_m`) with a regulation-height board face, and a 10 g dart held by jaw friction (ADR-0008).
2. Create `twin.yaml` with servo gains, torque and velocity limits, dart size, pad friction, board and mount geometry.
3. Script a planar flick (shoulder, elbow, wrist) with a timed jaw opening, and let the dart fly ballistically (no aero).
4. Search release time and joint targets for the throw that gets closest to the board centre, and report the result at several board distances.
5. Write `docs/v1-feasibility.md`.

**Demo:** `darts throw --scripted` prints the max release speed, the best throw and whether it lands on the board. `docs/v1-feasibility.md` tabulates board distances 0.9 to 1.2 m. The mp4 renders on RunPod once a GL backend is available.

**Rests on assumptions:** servo velocity limit 4.5 rad/s (datasheet 4.71, unmeasured), pad friction 1.0, and solver contact settings tuned in code (ADR-0008). If the real servo or pads differ, the feasible range moves.

### Test plan

#### End-to-end

- `darts throw --scripted` exits 0 only when the best throw hits the board at the twin's distance, and prints the verdict either way.
- Report records the feasible range edge (hit at 1.0 m, miss at 1.2 m).

#### Integration

- The dart stays pinched for 2 s at rest and through a hard swing with no release command.
- With a zero velocity limit the dart never leaves the gripper.
- A dart in free flight matches the closed-form arc within 1 mm.
- Opening the jaw releases the dart at a speed within the expected band.

#### Unit

- `twin.yaml` loader rejects unknown, missing or non-numeric keys and a wrong schema version.
- Jaw opens at the requested step.
- Sweep cost ranks valid hits above misses and invalid throws last.

## V2: Dart physics, board and scoring

**Delivers:** R2, R8 (scorer only)

**Build plan**

1. Add drag and restoring torque to the dart (ADR-0005), with coefficients in `twin.yaml`.
2. Build the board geometry (bull, outer bull, trebles, doubles, 20 segments) at the correct proportions and height.
3. Implement stick-or-bounce on tip contact.
4. Write a pure-Python scorer from a tip point to a score, and a 501 game state machine (three darts per turn, double-out, bust).

**Demo:** `darts drop --speed 5 --angle 25.7` launches a dart with no arm and prints a score of 60. No replay yet (video waits for RunPod). 501 logic is unit-tested, not yet played from the terminal.

**Built as:** `aero.py` (drag, fin torque, spin damping from `twin.yaml`), `board.py` (scorer), `game.py` (501), a collidable board face, and stop-at-first-contact sticking (ADR-0005). The V1 best throw at 1.0 m is chaotic in the jaw release (a tiny drag flips hit to bounce), so the search was re-run with aero on: still a stuck hit, 8 cm off centre after re-tuning for the fixed spin damping. Whether a dart sticks is very sensitive to dart attitude at arrival: one throw went from 196/200 stuck to 0/200 when spin damping changed tenfold. Later finding: that throw tumbled; the cross grip reaches 0.5 m (docs/v1-feasibility.md).

**Rests on assumptions:** Q3, Q4.

### Test plan

#### End-to-end

- A dart launched at a known point on the treble 20 sticks and scores 60.
- A dart launched too slowly falls short and scores 0.

#### Integration

- Dart with drag off lands within 1 mm of the closed-form arc, and with drag on, lands measurably shorter.
- A dart arriving at a grazing angle bounces off, and one arriving normally sticks.

#### Unit

- Scorer maps a table of 30 known board coordinates to their correct scores.
- 501 logic handles bust, double-out and checkout.

## V3: Gymnasium env with perfect state, plus a baseline

**Delivers:** R3 (partial), R4, R0 (partial)

**Build plan**

1. Define the state dataclass (ADR-0003) and the throw action (ADR-0004).
2. Wrap everything in `DartThrowEnv` with seeded resets and the distance reward.
3. Add `darts eval` with JSON output and a seed list.
4. Evaluate a random policy and a hand-tuned policy as baselines.

**Demo:** `darts eval --policy random --n 100` prints median and 90th percentile tip error and the hit rate, as JSON.

**Built as:** `interface.py` (state, 8-number action with `shoulder_pan` for aiming sideways), `env.py`, `policies.py`, `evaluate.py`. Baselines on 100 seeds (`docs/baselines/`): random 0% on board; hand-tuned (best V2 throw, panned to the target, height ignored) 97% on board and 78% stuck, median 9.0 cm, p90 22.5 cm. V4 has to beat that to reach 3 cm.

**Rests on assumptions:** Q13.

### Test plan

#### End-to-end

- Two evals with the same seed list produce identical JSON.
- Eval on a laptop smoke config (10 throws, CPU) finishes without error.

#### Integration

- Env reset then step returns a state matching the schema and an `info` flag for any clipped action.
- A NaN injected into the sim aborts the episode, logs the seed and counts as a miss.

#### Unit

- State dataclass round-trips to and from an array.
- Action decoder clips out-of-range parameters and flags it.

## V4: Train the throw policy on perfect state (RunPod)

**Delivers:** R0, R3

**Build plan**

1. Write the RunPod runner (bootstrap, sync code, run, pull artifacts, guaranteed teardown).
2. Train PPO on `DartThrowEnv` with target sampled across the whole board.
3. Save the policy and `metrics.json` to `runs/<id>/`.
4. Evaluate with a held-out seed list and render a replay mp4.

**Demo:** One command trains on a pod and tears it down. A replay mp4 of 10 throws at random targets lands on the board.

**Built so far:** `darts train` (PPO as a residual on the hand-tuned throw, since random throws never reach the board), `scripts/pod_train.sh` + `scripts/pod_job.sh` + vendored `scripts/rp` (dead-man's-switch, teardown, relay pull). Not yet run on a real pod: waiting on a RunPod key and a spend cap.

**Rests on assumptions:** Q13 (≥90% on board, median error ≤3 cm).

### Test plan

#### End-to-end

- Held-out eval of 100 throws meets Q13: at least 90% on board and median tip error at most 3 cm.
- After a run, the pod no longer exists (checked via the API).

#### Integration

- A deliberately failing job still triggers teardown.
- A pulled run directory contains the policy, metrics and replay.

#### Unit

- Runner builds the expected pod spec and the dead-man's-switch timeout.

## V5: Noise and domain randomisation

**Delivers:** R6

**Build plan**

1. Add observation noise on `target_in_base` and `board_normal_in_base`.
2. Randomise twin params each episode: servo gains, latency, jaw open time, friction, dart mass and aero coefficients, inside ranges in `twin.yaml`.
3. Retrain, then evaluate under the randomised twin and report degradation versus V4.

**Demo:** A table comparing V4 and V5 policies, each evaluated on the nominal and the randomised twin.

**Rests on assumptions:** randomisation ranges are guesses until real data exists.

### Test plan

#### End-to-end

- The V5 policy keeps at least 80% on-board and median error at most 5 cm under randomisation.
- The V5 policy is no worse than 1 cm median error worse than V4 on the nominal twin.

#### Integration

- Randomised params stay inside the declared ranges across 1000 samples.

#### Unit

- Noise injection is seeded and reproducible.

## V6: Virtual camera, unoccluded

**Delivers:** R5

**Build plan**

1. Add the mast and camera to the scene from `twin.yaml`.
2. Render 640×480 headless on a pod, confirming EGL or falling back to OSMesa.
3. Add a segmentation pass and an occlusion check across the whole throw.
4. Add a camera inset to the replay.

**Demo:** A replay with the camera view inset. A report shows the board's visible pixel fraction for each throw.

**Rests on assumptions:** EGL works on the chosen pod template (PLAN risk).

### Test plan

#### End-to-end

- Across 100 throws with the V5 policy, the board is at least 99% visible in every frame.

#### Integration

- A deliberately bad mast position, such as one behind the arm, fails the occlusion check.
- The same render on the pod and the laptop smoke config gives matching image size and intrinsics.

#### Unit

- Projection of a known 3D point through the camera matches its pixel to within 0.5 px.

## V7: State estimator, camera to policy

**Delivers:** R4, R5, R0 (full modular pipeline)

**Build plan**

1. Add a fiducial or ellipse board detector (OpenCV) that outputs board pose in the camera frame.
2. Convert to the state interface using the camera-to-base transform from `twin.yaml`.
3. Measure the estimator's error distribution under image noise, lighting variation and blur.
4. Feed that error into policy training, then run the full chain end to end.

**Demo:** A replay of a throw where the overlay shows the estimated and true board target, and the dart lands near it.

**Rests on assumptions:** the detector works at the board distance (0.5 m) with a 640×480 image (checked in the first build step).

### Test plan

#### End-to-end

- Camera, estimator, policy, throw: median tip error at most 4 cm on 100 seeded throws.

#### Integration

- Estimated target is within 1 cm of the true target at the board distance (0.5 m) for 95% of 500 random board poses.
- Policy trained with the V7 error model beats one trained on perfect state when the estimator is in the loop.

#### Unit

- Detector returns a clear failure value (not a pose) when the board is out of frame.
- Pixel-to-base conversion round-trips a known pose.

## V8: Play a game of 501

**Delivers:** R8

**Build plan**

1. Add a target-selection strategy (aim T20 early, set up doubles to finish).
2. Loop turns of three throws, resetting the dart into the gripper between throws (magic reset, since pick-up is out of scope).
3. Render a full game replay with the running score.

**Demo:** A full 501 game plays to a finish or a turn cap, with the scoreboard in the replay.

**Rests on assumptions:** Q13 accuracy. If accuracy is low, the game takes many turns, so the cap is 40 turns.

### Test plan

#### End-to-end

- A seeded game finishes or hits the 40-turn cap, and the final score matches the scorer's own sum.

#### Integration

- A bust resets the turn's score to the start-of-turn value.

#### Unit

- Strategy chooses a double for a remaining score of 40 and T20 for 501.

## V9: Hardware seam and sysid

**Delivers:** R7

**Build plan**

1. Define the `Arm` protocol, with `SimArm` and a `LeRobotArm` stub that logs trajectories to a common format.
2. Write the sysid fitter that adjusts gains, latency and jaw time to minimise joint-trajectory error.
3. Test it on synthetic logs, generated by a perturbed twin and treated as the "real" arm.

**Demo:** `darts sysid fit logs/` recovers a deliberately perturbed `twin.yaml` and prints before and after error.

**Rests on assumptions:** the real driver is LeRobot (Q6). Real hardware behaviour is untested until you have an arm.

### Test plan

#### End-to-end

- The fitter recovers servo gain and latency within 10% from synthetic logs with 1% noise.

#### Integration

- The same policy runs through `SimArm` and through the stub with a fake backend and produces the same commands.
- A test fails if a physical constant duplicates a `twin.yaml` key anywhere in the source.

#### Unit

- Log format round-trips a trajectory.
- Protocol methods reject malformed targets.
