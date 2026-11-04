"""Baseline policies. A policy maps a state to an action in [-1, 1]^8."""

from collections.abc import Callable

import numpy as np

from darts.interface import ACTION_DIM, State, encode_action
from darts.sim import ThrowParams

Policy = Callable[[State, np.random.Generator], np.ndarray]

# The best scripted throw at 0.5 m (cross grip, seed 11), aimed at the centre; it lands low on the
# board and sticks in about 80% of `darts robust` variants. Re-search after any grip or aero change.
_BEST = ThrowParams(
    q_start=(-0.84754557646579, -1.647533923825501, -1.3353654181703039),
    q_end=(0.5599011636721074, -0.23676876899022364, -0.8365615802655544),
    t_release_s=0.20881726682499185,
)


def random_policy(state: State, rng: np.random.Generator) -> np.ndarray:
    return rng.uniform(-1.0, 1.0, ACTION_DIM)


def hand_tuned_policy(state: State, rng: np.random.Generator) -> np.ndarray:
    """The fixed best throw, turned sideways to face the target. Height is ignored."""
    x, y, _ = state.target_in_base
    pan = -float(np.arctan2(y, x))  # positive shoulder_pan swings the arm towards -y
    return encode_action(ThrowParams(_BEST.q_start, _BEST.q_end, _BEST.t_release_s, pan))


POLICIES: dict[str, Policy] = {"random": random_policy, "hand": hand_tuned_policy}
