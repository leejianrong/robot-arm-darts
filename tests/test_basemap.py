import numpy as np
import pytest

from darts.basemap import (
    HIGH,
    LOW,
    _init_worker,
    basemap_policy,
    board_targets,
    features,
    fit,
    solve_target,
    start_vector,
)  # fmt: skip
from darts.interface import decode_action, target_state
from darts.sim import ThrowResult, assets_available
from darts.sweep import cost
from darts.twin import load_twin


def test_targets_cover_the_board_inside_its_radius():
    twin = load_twin()
    t = board_targets(twin, 60)
    assert t.shape == (60, 2)
    assert np.hypot(t[:, 0], t[:, 1]).max() < twin.board.radius_m
    assert t[:, 0].min() < -0.1 and t[:, 0].max() > 0.1 and t[:, 1].min() < -0.1


def solved_from(truth: np.ndarray, n: int = 40) -> list[dict]:
    rng = np.random.default_rng(0)
    out = []
    for y, z in rng.uniform(-0.12, 0.12, (n, 2)):
        x = np.clip(truth @ features(y, z), LOW, HIGH)
        out.append({"target": [y, z], "x": x.tolist(), "stuck": True, "miss_m": 0.01})
    return out


def test_fit_recovers_a_smooth_target_to_throw_map_and_the_policy_uses_it():
    twin = load_twin()
    mid = (LOW + HIGH) / 2
    truth = np.zeros((8, len(features(0.0, 0.0))))
    truth[:, 0] = mid
    truth[7, 1] = -0.5  # pan follows lateral offset
    truth[1, 2] = 0.8  # one joint follows height
    fitted = fit(solved_from(truth), centre_h=0.0)
    assert fitted and fitted["fit_rms"] < 1e-9
    state = target_state(twin, 0.05, -0.04)  # height is centre_h + z; centre_h given as 0 here
    state = type(state)(np.array([0.5, 0.05, -0.04]), state.board_normal_in_base, state.joint_pos)
    params, clipped = decode_action(basemap_policy(fitted)(state, np.random.default_rng(0)))
    want = truth @ features(0.05, -0.04)
    assert not clipped
    np.testing.assert_allclose([*params.q_start, *params.q_end], want[:6], atol=1e-9)
    assert params.pan_rad == pytest.approx(want[7])


def test_too_few_good_targets_gives_no_fit():
    bad = [{"target": [0, 0], "x": [0] * 8, "stuck": False, "miss_m": 0.5}] * 20
    assert fit(bad) is None


def test_the_cost_measures_distance_to_the_target_not_the_centre():
    r = ThrowResult(
        released=True, release_speed_m_s=3.0, release_angle_rad=0.7, release_height_m=1.6,
        crossed_plane=True, board_yz=(0.05, 0.0), shortfall_m=0.0, hit_board=True, stuck=True,
        arrival_angle_rad=0.2, arrival_speed_m_s=3.0,
    )  # fmt: skip
    assert cost(r, 2.0, target_yz=(0.05, 0.0)) < cost(r, 2.0) - 0.04


@pytest.mark.integration
@pytest.mark.skipif(not assets_available(), reason="run `make assets`")
def test_solve_target_returns_a_throw_and_how_close_it_got():
    twin = load_twin()
    _init_worker(twin)
    target = np.array([0.04, -0.03])
    s = solve_target((3, target, start_vector(twin, 0.04), 4, 0))
    assert s["idx"] == 3 and len(s["x"]) == 8 and s["miss_m"] >= 0 and s["evals"] > 0
    assert np.all(np.array(s["x"]) >= LOW - 1e-9) and np.all(np.array(s["x"]) <= HIGH + 1e-9)
