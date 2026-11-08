import pytest

from darts.board import Hit
from darts.game import Game

SINGLE = lambda n: Hit(n, "single", n)  # noqa: E731
DOUBLE = lambda n: Hit(2 * n, "double", n)  # noqa: E731
TREBLE = lambda n: Hit(3 * n, "treble", n)  # noqa: E731


def test_three_darts_make_a_turn_and_subtract():
    g = Game()
    for _ in range(3):
        assert g.throw(TREBLE(20)) == "ok"
    assert g.remaining == 501 - 180


def test_bust_restores_the_turn_start_and_ends_the_turn():
    g = Game(remaining=40)
    g.throw(SINGLE(20))
    assert g.throw(TREBLE(20)) == "bust"
    assert g.remaining == 40 and g.darts_in_turn == 0


def test_leaving_one_is_a_bust():
    g = Game(remaining=21)
    assert g.throw(SINGLE(20)) == "bust"
    assert g.remaining == 21


def test_reaching_zero_without_a_double_is_a_bust():
    g = Game(remaining=20)
    assert g.throw(SINGLE(20)) == "bust"
    assert not g.finished


def test_double_out_checks_out():
    g = Game(remaining=40)
    assert g.throw(DOUBLE(20)) == "checkout"
    assert g.finished and g.remaining == 0


def test_bullseye_counts_as_a_double():
    g = Game(remaining=50)
    assert g.throw(Hit(50, "bull")) == "checkout"


def test_turn_count_and_cap():
    from darts.game import MAX_TURNS

    g = Game()
    for _ in range(3 * MAX_TURNS):
        g.throw(SINGLE(1))
    assert g.turns == MAX_TURNS and g.over and not g.finished
    with pytest.raises(ValueError):
        g.throw(SINGLE(1))
