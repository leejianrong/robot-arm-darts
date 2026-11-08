import pytest

from darts.board import score_tip
from darts.game import Game
from darts.strategy import Target, aim_point, choose_target


def test_the_opening_dart_goes_at_treble_twenty_and_forty_goes_at_double_twenty():
    assert choose_target(501) == Target("treble", 20)
    assert choose_target(40) == Target("double", 20)
    assert choose_target(50) == Target("bull")
    assert choose_target(61) == Target("treble", 19)  # T20 would leave 1


def test_a_setup_dart_leaves_a_double():
    assert choose_target(41) == Target("single", 9)  # leaves 32
    assert choose_target(35) == Target("single", 3)


@pytest.mark.parametrize("remaining", range(2, 502))
def test_no_target_busts_the_turn_if_it_lands_where_aimed(remaining):
    target = choose_target(remaining)
    hit = score_tip(*aim_point(target))
    game = Game(remaining=remaining)
    assert game.throw(hit) != "bust"


def test_every_aim_point_scores_the_ring_and_segment_it_names():
    for ring in ("single", "double", "treble"):
        for segment in range(1, 21):
            hit = score_tip(*aim_point(Target(ring, segment)))
            assert (hit.ring, hit.segment) == (ring, segment)
    assert score_tip(*aim_point(Target("bull"))).points == 50
