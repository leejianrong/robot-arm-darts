import pytest

from darts.game import MAX_TURNS, START_SCORE
from darts.match import play
from darts.sim import ThrowParams, ThrowResult

PARAMS = ThrowParams((0.0,) * 3, (0.0,) * 3, 0.1)


def _result(stuck: bool, y: float = 0.0, z: float = 0.0) -> ThrowResult:
    return ThrowResult(True, 4.0, 0.1, 1.7, True, (y, z), 0.0, True, stuck=stuck)


def _always(stuck: bool, y: float, z: float):
    return lambda target, aim: (PARAMS, _result(stuck, y, z))


def _independent_remaining(log) -> int:
    """501 minus the darts of turns that did not bust, summed without using Game."""
    total, turns = 0, {}
    for r in log:
        turns.setdefault(r["turn"], []).append(r)
    for rows in turns.values():
        if all(r["outcome"] != "bust" for r in rows):
            total += sum(r["hit"].points for r in rows)
    return START_SCORE - total


def test_never_sticking_hits_the_cap_with_the_score_unchanged():
    game, log = play(_always(False, 0.0, 0.0))
    assert game.turns == MAX_TURNS and not game.finished
    assert len(log) == 3 * MAX_TURNS and game.remaining == START_SCORE


def test_perfect_bull_thrower_finishes_and_the_score_is_the_sum():
    from darts.board import score_tip

    def thrower(target, aim):  # lands exactly on the aim point
        return PARAMS, _result(True, *aim)

    game, log = play(thrower)
    assert game.finished and game.remaining == 0
    assert _independent_remaining(log) == 0
    assert score_tip(*log[-1]["aim_yz_m"]).points == log[-1]["hit"].points


def test_log_matches_independent_sum_when_busts_happen():
    # a thrower that hits the bull every time busts once the score is small
    game, log = play(_always(True, 0.0, 0.0))
    assert any(r["outcome"] == "bust" for r in log)
    assert game.remaining == _independent_remaining(log)
    assert game.over


@pytest.mark.integration
def test_real_sim_game_ends_and_its_score_is_the_sum():
    from darts.match import sim_thrower
    from darts.policies import hand_tuned_policy
    from darts.twin import load_twin

    twin = load_twin("twin.yaml")
    game, log = play(sim_thrower(twin, hand_tuned_policy, 0))
    assert game.over
    assert game.remaining == _independent_remaining(log)
