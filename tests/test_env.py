import numpy as np
import pytest

from darts.env import INVALID_REWARD, DartThrowEnv
from darts.evaluate import evaluate
from darts.interface import ACTION_DIM, STATE_DIM
from darts.policies import POLICIES
from darts.sim import NO_POINT, ThrowResult, assets_available
from darts.twin import load_twin


class FakeSim:
    """Stands in for ThrowSim so the env logic runs without the SO-101 assets."""

    def __init__(self, result: ThrowResult):
        self.result = result

    def throw(self, params):
        return self.result


def result(**kw):
    base = dict(
        released=True, release_speed_m_s=3.0, release_angle_rad=0.7, release_height_m=1.6,
        crossed_plane=True, board_yz=(0.0, 0.0), shortfall_m=0.0, hit_board=True, stuck=True,
    )  # fmt: skip
    return ThrowResult(**(base | kw))


def env_with(res):
    return DartThrowEnv(load_twin(), sim=FakeSim(res))


def test_solver_divergence_aborts_and_counts_as_a_miss(caplog):
    env = env_with(result(diverged=True, board_yz=NO_POINT))
    env.reset(seed=7)
    with caplog.at_level("WARNING"):
        _, reward, done, _, info = env.step(np.zeros(ACTION_DIM))
    assert done and reward == INVALID_REWARD and info["invalid"] and info["diverged"]
    assert "seed=7" in caplog.text


def test_closer_tip_earns_more_reward():
    env = env_with(result())
    _, info = env.reset(seed=3)
    y, z = info["target_yz_m"]
    env.sim.result = result(board_yz=(y + 0.01, z))
    r_near = env.step(np.zeros(ACTION_DIM))[1]
    env.sim.result = result(board_yz=(y + 0.10, z))
    r_far = env.step(np.zeros(ACTION_DIM))[1]
    assert r_near > r_far


def test_step_flags_a_clipped_action():
    env = env_with(result())
    env.reset(seed=0)
    assert env.step(np.full(ACTION_DIM, 3.0))[4]["clipped"]


def test_reset_gives_the_state_schema_and_is_seeded():
    env = env_with(result())
    a, _ = env.reset(seed=11)
    b, _ = env.reset(seed=11)
    c, _ = env.reset(seed=12)
    assert a.shape == (STATE_DIM,)
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)


needs_assets = pytest.mark.skipif(not assets_available(), reason="run `make assets`")


@pytest.mark.integration
@needs_assets
def test_same_seed_gives_identical_outcomes():
    env = DartThrowEnv(load_twin())
    outs = []
    for _ in range(2):
        env.reset(seed=5)
        _, reward, _, _, info = env.step(POLICIES["hand"](env.state(), np.random.default_rng(5)))
        outs.append((reward, info["score"], info["tip_error_m"]))
    assert outs[0] == outs[1]


@pytest.mark.integration
@needs_assets
def test_two_evals_with_the_same_seeds_give_identical_json():
    env = DartThrowEnv(load_twin())
    first = evaluate(env, POLICIES["hand"], list(range(10)))
    second = evaluate(env, POLICIES["hand"], list(range(10)))
    assert first == second
    assert first["n"] == 10  # the laptop smoke config
