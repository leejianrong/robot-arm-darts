"""Gymnasium env: one episode is one throw at a target on the board (ADR-0004)."""

import logging
from typing import Any

import gymnasium as gym
import numpy as np

from darts.interface import ACTION_DIM, STATE_DIM, State, decode_action, target_state
from darts.sim import ThrowResult, ThrowSim
from darts.twin import Twin

log = logging.getLogger(__name__)
INVALID_REWARD = -2.0  # the arm failed to make a throw at all (slip, collision, solver blow-up)
SHORT_REWARD = -1.0  # the dart never reached the board; shortfall is subtracted on top
BOUNCE_PENALTY = 0.2  # a dart that hits but does not stick is not a hit (PPO farmed bounces)


class DartThrowEnv(gym.Env):
    """Observation is the state interface, action is the throw (see `interface.py`).

    Reward is the negative distance from where the dart met the board to the target, plus a
    penalty if it does not stick, and no tip error is reported. Terminates after the single step.
    """

    metadata = {"render_modes": []}

    def __init__(self, twin: Twin, sim: ThrowSim | None = None):
        self.twin = twin
        self.sim = sim or ThrowSim(twin)
        self.observation_space = gym.spaces.Box(-np.inf, np.inf, (STATE_DIM,), np.float64)
        self.action_space = gym.spaces.Box(-1.0, 1.0, (ACTION_DIM,), np.float64)
        self._target = (0.0, 0.0)
        self._seed: int | None = None

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        self._seed = seed
        r = self.twin.board.radius_m * np.sqrt(self.np_random.uniform())  # uniform over the disc
        a = self.np_random.uniform(0.0, 2.0 * np.pi)
        self._target = (float(r * np.cos(a)), float(r * np.sin(a)))  # (z offset, y offset)
        return self._obs(), {"target_yz_m": (self._target[1], self._target[0])}

    def _obs(self) -> np.ndarray:
        z, y = self._target
        return target_state(self.twin, y, z).to_array()

    def _reward(self, r: ThrowResult) -> tuple[float, float | None]:
        """(reward, tip-to-target distance, or None if the dart did not reach the board)."""
        if not r.released or r.slipped_early or r.diverged or r.collided:
            return INVALID_REWARD, None
        if not r.hit_board:
            return SHORT_REWARD - r.shortfall_m if not r.crossed_plane else -r.miss_m, None
        y, z = r.board_yz
        dist = float(np.hypot(y - self._target[1], z - self._target[0]))
        return (-dist, dist) if r.stuck else (-dist - BOUNCE_PENALTY, None)

    def step(self, action: np.ndarray):
        params, clipped = decode_action(np.asarray(action, dtype=np.float64))
        result = self.sim.throw(params)
        if result.diverged:
            log.warning("solver diverged on episode seed=%s; counted as a miss", self._seed)
        reward, dist = self._reward(result)
        info: dict[str, Any] = {
            "clipped": clipped,
            "invalid": reward == INVALID_REWARD,
            "diverged": result.diverged,
            "stuck": result.stuck,
            "score": result.score,
            "tip_error_m": dist,
            "seed": self._seed,
        }
        return self._obs(), reward, True, False, info

    def state(self) -> State:
        return State.from_array(self._obs())
