"""Seeded evaluation of a policy on the throw env."""

import numpy as np

from darts.env import DartThrowEnv
from darts.policies import Policy

TARGET_ON_BOARD = 0.9  # fraction of throws that must reach the board (PLAN Q13)
TARGET_MEDIAN_M = 0.03  # median tip-to-target distance


def evaluate(env: DartThrowEnv, policy: Policy, seeds: list[int]) -> dict:
    """Run one throw per seed. Tip error counts as infinite for throws that miss the board."""
    errors, stuck, scores = [], 0, []
    for seed in seeds:
        obs, _ = env.reset(seed=seed)
        rng = np.random.default_rng(seed)
        _, _, _, _, info = env.step(policy(env.state(), rng))
        err = info["tip_error_m"]
        errors.append(np.inf if err is None else err)
        stuck += info["stuck"]
        scores.append(info["score"])
    e = np.array(errors)
    on_board = float(np.mean(np.isfinite(e)))
    median = float(np.percentile(e, 50, method="higher"))
    p90 = float(np.percentile(e, 90, method="higher"))
    return {
        "n": len(seeds),
        "seeds": [seeds[0], seeds[-1]],
        "on_board_rate": on_board,
        "stuck_rate": stuck / len(seeds),
        "median_tip_error_m": median if np.isfinite(median) else None,
        "p90_tip_error_m": p90 if np.isfinite(p90) else None,
        "mean_score": float(np.mean(scores)),
        "meets_q13": bool(on_board >= TARGET_ON_BOARD and median <= TARGET_MEDIAN_M),
    }
