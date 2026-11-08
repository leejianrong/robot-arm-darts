import numpy as np
import pytest

from darts.env import DartThrowEnv
from darts.randomise import sample
from darts.sim import assets_available
from darts.twin import load_twin


def test_a_thousand_samples_stay_inside_the_declared_ranges():
    twin, rng = load_twin("twin.yaml"), np.random.default_rng(0)
    r = twin.randomise
    pairs = {  # twin field -> the fraction it may move
        ("servo", "kp"): r.servo_gain_frac,
        ("servo", "kv"): r.servo_gain_frac,
        ("servo", "torque_limit_nm"): r.servo_torque_frac,
        ("dart", "mass_kg"): r.dart_mass_frac,
        ("release", "pad_friction"): r.pad_friction_frac,
        ("aero", "drag_kg_m"): r.drag_frac,
        ("aero", "fin_torque_nm"): r.fin_torque_frac,
        ("aero", "spin_damping_nm_s"): r.spin_damping_frac,
    }

    def value(t, key):
        return getattr(getattr(t, key[0]), key[1])

    seen: dict[tuple[str, str], list[float]] = {k: [] for k in pairs}
    for _ in range(1000):
        t = sample(twin, rng)
        for key, frac in pairs.items():
            v = value(t, key) / value(twin, key)
            assert 1 - frac <= v <= 1 + frac, key
            seen[key].append(v)
    for key, frac in pairs.items():  # and they really spread over it
        assert max(seen[key]) - min(seen[key]) > 1.8 * frac, key


def test_the_things_that_are_not_uncertain_do_not_move():
    twin = load_twin("twin.yaml")
    t = sample(twin, np.random.default_rng(1))
    assert (t.board, t.mount, t.camera, t.sim, t.power) == (
        twin.board,
        twin.mount,
        twin.camera,
        twin.sim,
        twin.power,
    )


def test_the_same_seed_draws_the_same_twin():
    twin = load_twin("twin.yaml")
    assert sample(twin, np.random.default_rng(5)) == sample(twin, np.random.default_rng(5))


@pytest.mark.integration
@pytest.mark.skipif(not assets_available(), reason="run `make assets`")
def test_a_randomising_env_gives_each_seed_its_own_arm_and_repeats_it():
    env = DartThrowEnv(load_twin("twin.yaml"), randomise=True)
    env.reset(seed=1)
    first = env.twin
    env.reset(seed=2)
    assert env.twin != first
    env.reset(seed=1)
    assert env.twin == first
