import numpy as np
import pytest

from darts.arm import SimArm, plan, run
from darts.sim import ThrowParams, ThrowSim, assets_available
from darts.sysid import fit, states_of, with_params
from darts.twin import load_twin

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not assets_available(), reason="run `make assets`"),
]

THROWS = [
    ThrowParams((-0.85, -1.65, -1.34), (0.56, -0.24, -0.84), 0.21),
    ThrowParams((-0.6, -1.2, -1.0), (0.9, -0.5, -0.6), 0.25, 0.1),
    ThrowParams((-1.0, -1.8, -1.4), (0.3, 0.0, -0.3), 0.15, -0.1),
]
LATENCY, JAW = 0.03, 0.025


def synthetic_logs(twin, gain: float, noise: float, seed: int = 0) -> list[list[dict]]:
    """Logs from a servo with the given gain ratio and delays; `noise` is the Gaussian std on each
    joint as a fraction of that joint's range over the log."""
    true = with_params(twin, twin.servo.kp * gain, twin.servo.kv * gain, LATENCY, JAW)
    rng = np.random.default_rng(seed)
    logs = []
    for p in THROWS:
        log = run(SimArm(ThrowSim(true)), plan(p))
        sd = noise * np.ptp(states_of(log), axis=0)
        for e in log:
            if e["kind"] == "state":
                e["joint_pos"] = list(np.array(e["joint_pos"]) + rng.normal(0, 1, 6) * sd)
        logs.append(log)
    return logs


def test_latency_and_jaw_delay_recovered_within_10_percent_at_1_percent_noise():
    twin = load_twin("twin.yaml")
    r = fit(twin, synthetic_logs(twin, gain=1.0, noise=0.01))
    assert r["latency_s"] == pytest.approx(LATENCY, rel=0.1)
    assert r["jaw_delay_s"] == pytest.approx(JAW, rel=0.1)
    assert r["rms_after_rad"] < r["rms_before_rad"] / 3


def test_gain_recovered_from_clean_logs():
    twin = load_twin("twin.yaml")
    r = fit(twin, synthetic_logs(twin, gain=0.6, noise=0.0))
    assert r["gain_ratio"] == pytest.approx(0.6, rel=0.1)


def test_gain_is_reported_as_undetermined_at_1_percent_noise():
    # a stiff servo barely changes the joint trajectory, so noise hides the gain: the fit must
    # say so rather than hand back a confident wrong number
    twin = load_twin("twin.yaml")
    r = fit(twin, synthetic_logs(twin, gain=1.2, noise=0.01))
    assert r["stderr"]["gain_ratio"] > 0.1 * r["gain_ratio"]
    assert r["stderr"]["latency_s"] < 0.1 * r["latency_s"]
