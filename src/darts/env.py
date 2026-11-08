"""Gymnasium env: one episode is one throw at a target on the board (ADR-0004)."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np

from darts.interface import ACTION_DIM, STATE_DIM, State, decode_action, target_state
from darts.sim import ThrowResult, ThrowSim
from darts.sweep import throw_penalty
from darts.twin import Twin

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ObsNoise:
    """Seeded error added to what the policy sees of the board, not to where the board is."""

    target_std_m: tuple[float, float, float] = (0.0, 0.0, 0.0)  # per axis, arm base frame
    normal_std_rad: float = 0.0  # random tilt of the board normal

    @classmethod
    def from_estimator_json(cls, path: str) -> "ObsNoise":
        """The degraded-frame error model that `darts estimate` writes (docs/baselines)."""
        m = json.loads(Path(path).read_text())
        sx, sy, sz = m["target_std_m"]
        return cls((sx, sy, sz), m["normal_error_rad"]["p95"] / 2)  # p95 is about 2 sigma

    def apply(self, state: State, rng: np.random.Generator) -> State:
        target = state.target_in_base + rng.normal(0.0, 1.0, 3) * np.array(self.target_std_m)
        normal = state.board_normal_in_base + rng.normal(0.0, self.normal_std_rad, 3)
        return State(target, normal / np.linalg.norm(normal), state.joint_pos)


INVALID_REWARD = -2.0  # the arm failed to make a throw at all (slip, collision, solver blow-up)
SHORT_REWARD = -1.0  # the dart never reached the board; shortfall is subtracted on top
MAX_MISS_M = 1.0  # a dart that lands far off the board is no worse than one 1 m away


class DartThrowEnv(gym.Env):
    """Observation is the state interface, action is the throw (see `interface.py`).

    Reward is the negative distance from where the dart met the board plane to the target, minus
    the search's arrival penalties (slant, too slow, bouncing: PPO farmed bounces when they paid).
    Only a stuck dart reports a tip error. Terminates after the single step.
    """

    metadata = {"render_modes": []}

    def __init__(self, twin: Twin, sim: ThrowSim | None = None, noise: ObsNoise | None = None):
        self.twin = twin
        self.noise = noise or ObsNoise()
        self._obs_now = np.zeros(STATE_DIM)
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
        z, y = self._target
        clean = target_state(self.twin, y, z)
        self._obs_now = self.noise.apply(clean, self.np_random).to_array()  # same seed, same noise
        return self._obs(), {"target_yz_m": (self._target[1], self._target[0])}

    def _obs(self) -> np.ndarray:
        return self._obs_now

    def _reward(self, r: ThrowResult) -> tuple[float, float | None]:
        """(reward, tip-to-target distance, or None if the dart did not reach the board)."""
        if not r.released or r.slipped_early or r.diverged or r.collided:
            return INVALID_REWARD, None
        if not r.crossed_plane:
            return SHORT_REWARD - r.shortfall_m, None
        y, z = r.board_yz
        dist = float(np.hypot(y - self._target[1], z - self._target[0]))
        reward = -min(dist, MAX_MISS_M) - throw_penalty(r, self.twin.board.stick_min_speed_m_s)
        return reward, dist if r.stuck else None  # only a stuck dart counts as a hit

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
