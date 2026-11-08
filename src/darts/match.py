"""A full 501 game (DART-27): aim by strategy, throw, score, repeat until out or the turn cap.

The dart goes back in the gripper between throws by resetting the sim (no pick-up)."""

from collections.abc import Callable

import numpy as np

from darts.board import Hit, score_tip
from darts.game import Game
from darts.interface import decode_action, target_state
from darts.policies import Policy
from darts.sim import ThrowParams, ThrowResult, ThrowSim
from darts.strategy import Target, aim_point, choose_target
from darts.twin import Twin

MISS = Hit(0, "miss")
# (target, aim offset (y, z) from the board centre) -> (params, result)
Thrower = Callable[[Target, tuple[float, float]], tuple[ThrowParams, ThrowResult]]


def sim_thrower(twin: Twin, policy: Policy, seed: int, sim: ThrowSim | None = None) -> Thrower:
    sim = sim or ThrowSim(twin)
    rng = np.random.default_rng(seed)

    def throw(target: Target, aim: tuple[float, float]):
        params, _ = decode_action(policy(target_state(twin, *aim), rng))
        return params, sim.throw(params)

    return throw


def hit_of(r: ThrowResult) -> Hit:
    """What the scorer sees: only a dart that stuck scores, at the point it met the board."""
    if not r.stuck:
        return MISS
    y, z = r.board_yz
    return score_tip(y, z)


def play(thrower: Thrower) -> tuple[Game, list[dict]]:
    """Play one game. The log has a row per dart: turn, target, aim, params, hit and score after."""
    game, log = Game(), []
    while not game.over:
        turn = game.turns
        target = choose_target(game.remaining)
        aim = aim_point(target)
        params, result = thrower(target, aim)
        hit = hit_of(result)
        outcome = game.throw(hit)
        log.append(
            {
                "turn": turn + 1,
                "target": f"{target.ring} {target.segment or ''}".strip(),
                "aim_yz_m": aim,
                "params": params,
                "stuck": result.stuck,
                "hit": hit,
                "outcome": outcome,
                "remaining": game.remaining,
            }
        )
    return game, log
