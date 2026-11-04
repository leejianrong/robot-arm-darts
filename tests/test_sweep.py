from darts.sim import ThrowResult
from darts.sweep import cost


def result(**kw):
    base = dict(
        released=True,
        release_speed_m_s=3.0,
        release_angle_rad=0.7,
        release_height_m=1.6,
        crossed_plane=True,
        board_yz=(0.0, 0.1),
        shortfall_m=0.0,
        hit_board=True,
    )
    if "miss_m" in kw:
        kw["board_yz"] = (0.0, kw.pop("miss_m"))
    base.update(kw)
    return ThrowResult(**base)


def test_closer_hit_costs_less():
    assert cost(result(miss_m=0.05)) < cost(result(miss_m=0.15))


def test_falling_short_costs_more_than_any_crossing():
    assert cost(
        result(crossed_plane=False, miss_m=float("inf"), shortfall_m=0.3, hit_board=False)
    ) > cost(result(miss_m=1.0))


def test_shorter_shortfall_is_better():
    short = result(crossed_plane=False, miss_m=float("inf"), hit_board=False)
    assert cost(result(**{**short.__dict__, "shortfall_m": 0.1})) < cost(
        result(**{**short.__dict__, "shortfall_m": 0.5})
    )


def test_invalid_throws_rank_last():
    worst_valid = cost(
        result(crossed_plane=False, miss_m=float("inf"), shortfall_m=5.0, hit_board=False)
    )
    for flag in ("slipped_early", "diverged", "collided"):
        assert cost(result(**{flag: True})) > worst_valid
    assert cost(result(released=False)) > worst_valid


def test_a_bounce_costs_more_than_a_dart_that_sticks():
    assert cost(result(stuck=False, miss_m=0.01)) > cost(result(stuck=True, miss_m=0.15))
