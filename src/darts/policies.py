"""Baseline policies. A policy maps a state to an action in [-1, 1]^8."""

from collections.abc import Callable

import numpy as np

from darts.interface import ACTION_DIM, State, encode_action
from darts.sim import ThrowParams

Policy = Callable[[State, np.random.Generator], np.ndarray]

# The best scripted throw at 1.0 m (V2 sweep, seed 1). It aims straight ahead at the centre.
_BEST = ThrowParams(
    q_start=(-1.2691771656801212, -1.6484029807819554, -1.2818110129976354),
    q_end=(0.29811470728461614, 1.3062195566002077, 0.5185272982128247),
    t_release_s=0.18056548625667213,
)


def random_policy(state: State, rng: np.random.Generator) -> np.ndarray:
    return rng.uniform(-1.0, 1.0, ACTION_DIM)


def hand_tuned_policy(state: State, rng: np.random.Generator) -> np.ndarray:
    """The fixed best throw, turned sideways to face the target. Height is ignored."""
    x, y, _ = state.target_in_base
    pan = -float(np.arctan2(y, x))  # positive shoulder_pan swings the arm towards -y
    return encode_action(ThrowParams(_BEST.q_start, _BEST.q_end, _BEST.t_release_s, pan))


POLICIES: dict[str, Policy] = {"random": random_policy, "hand": hand_tuned_policy}
