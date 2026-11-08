# System identification (DART-30)

`darts sysid LOG... ` fits the servo gain, the servo latency and the jaw delay to arm logs by
replaying each log's commands on the sim and minimising the joint-position error
(`src/darts/sysid.py`). A log is what `darts.arm.run` writes (`write_log`), from the sim or from the
real arm through `LeRobotArm`. The twin has `servo.latency_s` and `release.jaw_delay_s`, both 0
until measured. The output is JSON: the fitted values, a one-sigma `stderr` for each, and the RMS
error before and after.

## What a log can tell you (synthetic logs, three throws, 50 Hz, noise as a fraction of each joint's range)

| Truth | Noise | Gain ratio fitted | Latency fitted (true 30 ms) | Jaw delay fitted (true 25 ms) | Gain stderr |
|---|---|---|---|---|---|
| gain 0.5 | 1% | 0.85 | 28.2 ms | 26.4 ms | 0.43 |
| gain 0.5 | 0.1% | 0.56 | 28.2 ms | 27.3 ms | 0.02 |
| gain 1.2 | 0.1% | 0.91 | 28.1 ms | 26.5 ms | 0.04 |
| gain 1.2 | none | 1.20 | 28.2 ms | 26.4 ms | 0 |

- **Latency and jaw delay** come back within 10% at 1% noise (the 2 ms sim step and the tie between the two leave a 2 to 6% bias).
- **Servo gain does not.** The modelled servo is stiff (kp 998 against a 2.94 N m torque limit), so a 20% gain change moves a joint by 0.1 mrad against a range of 1.6 rad; 1% noise buries it, and at 0.1% the fit is still 25% off in one case while its stderr claims 4%. Use the `stderr`: when it is not well under 10% of the gain, the logs did not determine the gain, and the datasheet value stays.
- To measure gain on hardware, excite it: a log of a loaded, slow joint, or a faster state rate than 50 Hz. Latency and jaw delay need only the normal throw logs.
- kp and kv are fitted as one ratio (as `randomise` varies them): a log cannot separate them (fitting both gave kp 15% off).
