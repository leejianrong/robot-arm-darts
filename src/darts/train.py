# pyright: reportMissingImports=false
"""PPO on the throw env, as a residual on the hand-tuned throw (needs the `train` extra).

A random policy never reaches the board, so PPO from scratch sees no signal. The learned part is
a correction `scale * a` added to the hand-tuned action instead.
"""

import json
import time
from pathlib import Path

import gymnasium as gym
import numpy as np

from darts.env import DartThrowEnv
from darts.evaluate import evaluate
from darts.interface import State
from darts.policies import Policy, hand_tuned_policy
from darts.twin import Twin

HELD_OUT_SEEDS = list(range(10_000, 10_100))  # never used for training resets


class ResidualEnv(gym.Wrapper):
    """The agent's action is a correction to the hand-tuned throw for the current target."""

    def __init__(self, env: DartThrowEnv, scale: float):
        super().__init__(env)
        self._dart = env
        self.scale = scale
        self._state: State | None = None
        self._rng = np.random.default_rng(0)  # unused by the hand policy, which is deterministic

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self._state = self._dart.state()
        return obs, info

    def step(self, action):
        assert self._state is not None
        base = hand_tuned_policy(self._state, self._rng)
        return self.env.step(np.clip(base + self.scale * np.asarray(action), -1.0, 1.0))


def learned_policy(model, scale: float) -> Policy:
    def policy(state: State, rng: np.random.Generator) -> np.ndarray:
        correction, _ = model.predict(state.to_array(), deterministic=True)
        return np.clip(hand_tuned_policy(state, rng) + scale * correction, -1.0, 1.0)

    return policy


def load_policy(path: str | Path) -> Policy:
    """Load a policy saved by `train` (policy.zip with a policy.json beside it)."""
    from stable_baselines3 import PPO

    path = Path(path)
    scale = json.loads(path.with_suffix(".json").read_text())["scale"]
    return learned_policy(PPO.load(path, device="cpu"), scale)


def train(twin: Twin, steps: int, n_envs: int, seed: int, scale: float, out: Path) -> dict:
    from stable_baselines3 import PPO
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

    def make():
        return Monitor(ResidualEnv(DartThrowEnv(twin), scale))  # Monitor logs ep_rew_mean

    venv = (
        SubprocVecEnv([make] * n_envs, start_method="forkserver")
        if n_envs > 1
        else DummyVecEnv([make])
    )
    model = PPO(
        "MlpPolicy", venv, n_steps=64, batch_size=256, n_epochs=10, learning_rate=3e-4,
        policy_kwargs={"log_std_init": -1.0, "net_arch": [64, 64]}, seed=seed, device="cpu",
        verbose=1,
    )  # fmt: skip
    start = time.time()
    model.learn(total_timesteps=steps)
    venv.close()
    seconds = time.time() - start

    out.mkdir(parents=True, exist_ok=True)
    model.save(out / "policy")
    (out / "policy.json").write_text(json.dumps({"scale": scale}))
    env = DartThrowEnv(twin)
    metrics = {
        "config": {"steps": steps, "n_envs": n_envs, "seed": seed, "scale": scale},
        "train_seconds": round(seconds, 1),
        "baseline_hand": evaluate(env, hand_tuned_policy, HELD_OUT_SEEDS),
        "held_out": evaluate(env, learned_policy(model, scale), HELD_OUT_SEEDS),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics
