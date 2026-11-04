"""Baseline policies. A policy maps a state to an action in [-1, 1]^8."""

from collections.abc import Callable

import numpy as np

from darts.interface import ACTION_DIM, State, encode_action
from darts.sim import ThrowParams

Policy = Callable[[State, np.random.Generator], np.ndarray]

# The best scripted throw at 1.0 m (seed 1, searched after the spin-damping fix), aimed at the
# centre. Whether it sticks is knife-edge in the twin: re-search after any aero change.
_BEST = ThrowParams(
    q_start=(-1.3921612132548298, -1.589493535275797, -1.2271570582911078),
    q_end=(1.23160442594621, -0.7088024495858529, 0.003932529510716521),
    t_release_s=0.19277793609829927,
)


def random_policy(state: State, rng: np.random.Generator) -> np.ndarray:
    return rng.uniform(-1.0, 1.0, ACTION_DIM)


def hand_tuned_policy(state: State, rng: np.random.Generator) -> np.ndarray:
    """The fixed best throw, turned sideways to face the target. Height is ignored."""
    x, y, _ = state.target_in_base
    pan = -float(np.arctan2(y, x))  # positive shoulder_pan swings the arm towards -y
    return encode_action(ThrowParams(_BEST.q_start, _BEST.q_end, _BEST.t_release_s, pan))


POLICIES: dict[str, Policy] = {"random": random_policy, "hand": hand_tuned_policy}
