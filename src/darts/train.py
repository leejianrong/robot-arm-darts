# pyright: reportMissingImports=false
"""PPO on the throw env, as a residual on the hand-tuned throw (needs the `train` extra).

A random policy never reaches the board, so PPO from scratch sees no signal. The learned part is
a correction `scale * a` added to the hand-tuned action instead.
"""

import dataclasses
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
PROGRESS_SEEDS = HELD_OUT_SEEDS[:30]  # the quick eval at each checkpoint
AERO_CORNERS = ((0.5, 0.3, 0.5), (2.0, 3.0, 1.5))  # (fin torque, spin damping, drag) multipliers
MAX_DIVERGED_RATE = 0.01
MAX_RAM_PCT = 90
REGRESSION = 0.25  # abort if on-board rate falls this far below the hand throw's, after warm-up
WARMUP_EVALS = 3


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


def _ram_pct() -> float:
    m = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    kb = {k: float(v.split()[0]) for k, v in m.items() if k in ("MemTotal", "MemAvailable")}
    return 100.0 * (1.0 - kb["MemAvailable"] / kb["MemTotal"])


def _callback(twin: Twin, scale: float, out: Path, eval_every: int, max_seconds: float | None):
    """Every `eval_every` steps: held-out eval, checkpoint, one EVAL line, and the abort rules.

    The abort reason goes in the log as `ABORT <why>` and in `out/abort.txt`; the run still saves
    its policy and publishes, so a stopped run is readable, not lost.
    """
    from stable_baselines3.common.callbacks import BaseCallback

    class Progress(BaseCallback):
        def __init__(self):
            super().__init__()
            self.env = DartThrowEnv(twin)
            self.start = time.time()
            self.next_eval = eval_every
            self.throws = self.diverged = 0
            self.base_on_board: float | None = None
            self.evals = 0
            self.abort = ""

        def _on_step(self) -> bool:
            infos = self.locals["infos"]
            self.throws += len(infos)
            self.diverged += sum(bool(i["diverged"]) for i in infos)
            if self.num_timesteps >= self.next_eval:
                self.next_eval += eval_every
                self.abort = self._checkpoint()
            elapsed = time.time() - self.start
            if not self.abort and max_seconds is not None and elapsed > max_seconds:
                self.abort = f"time budget {max_seconds:.0f}s used"
            if not self.abort and _ram_pct() > MAX_RAM_PCT:
                self.abort = f"RAM above {MAX_RAM_PCT}%"
            if self.abort:
                print(f"ABORT {self.abort}", flush=True)
                (out / "abort.txt").write_text(self.abort)
            return not self.abort

        def _checkpoint(self) -> str:
            if self.base_on_board is None:
                hand = evaluate(self.env, hand_tuned_policy, PROGRESS_SEEDS)
                self.base_on_board = hand["on_board_rate"]
            base = float(self.base_on_board)  # type: ignore[arg-type]
            ev = evaluate(self.env, learned_policy(self.model, scale), PROGRESS_SEEDS)
            rate = self.diverged / max(self.throws, 1)
            row = {
                "steps": self.num_timesteps,
                "seconds": round(time.time() - self.start),
                "on_board": ev["on_board_rate"],
                "stuck": ev["stuck_rate"],
                "median_m": ev["median_tip_error_m"],
                "hand_on_board": base,
                "train_throws": self.throws,
                "diverged_rate": round(rate, 4),
            }
            with (out / "metrics.jsonl").open("a") as f:
                f.write(json.dumps(row) + "\n")
            self.model.save(out / "checkpoint")
            print("EVAL " + " ".join(f"{k}={v}" for k, v in row.items()), flush=True)
            self.evals += 1
            if rate > MAX_DIVERGED_RATE and self.throws >= 200:
                return f"diverged rate {rate:.1%} over {self.throws} throws"
            if self.evals >= WARMUP_EVALS and ev["on_board_rate"] < base - REGRESSION:
                return f"on-board {ev['on_board_rate']:.0%} vs hand {base:.0%}"
            return ""

    return Progress()


def _aero_variant(twin: Twin, fin: float, damp: float, drag: float) -> Twin:
    a = twin.aero
    return dataclasses.replace(
        twin,
        aero=dataclasses.replace(
            a,
            fin_torque_nm=a.fin_torque_nm * fin,
            spin_damping_nm_s=a.spin_damping_nm_s * damp,
            drag_kg_m=a.drag_kg_m * drag,
        ),
    )


def train(
    twin: Twin, steps: int, n_envs: int, seed: int, scale: float, out: Path,
    eval_every: int = 10_000, max_seconds: float | None = None,
) -> dict:  # fmt: skip
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
    out.mkdir(parents=True, exist_ok=True)
    progress = _callback(twin, scale, out, eval_every, max_seconds)
    start = time.time()
    model.learn(total_timesteps=steps, callback=progress)
    venv.close()
    seconds = time.time() - start

    model.save(out / "policy")
    (out / "policy.json").write_text(json.dumps({"scale": scale}))
    env = DartThrowEnv(twin)
    learned = learned_policy(model, scale)
    robust = {  # a policy that only works at the nominal aero numbers is not a result
        str(c): evaluate(DartThrowEnv(_aero_variant(twin, *c)), learned, PROGRESS_SEEDS)
        for c in AERO_CORNERS
    }
    metrics = {
        "config": {"steps": steps, "n_envs": n_envs, "seed": seed, "scale": scale},
        "train_seconds": round(seconds, 1),
        "aborted": progress.abort or None,
        "train_throws": progress.throws,
        "train_diverged": progress.diverged,
        "aero_corners": robust,
        "baseline_hand": evaluate(env, hand_tuned_policy, HELD_OUT_SEEDS),
        "held_out": evaluate(env, learned, HELD_OUT_SEEDS),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics
