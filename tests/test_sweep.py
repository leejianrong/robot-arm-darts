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


def test_a_slanted_arrival_costs_more_than_a_square_one():
    square = result(arrival_angle_rad=0.1)
    slanted = result(arrival_angle_rad=1.2)
    assert cost(slanted) > cost(square) + 0.1


def test_square_arrival_limit():
    from darts.sweep import square_arrival

    assert square_arrival(result(arrival_angle_rad=0.3))
    assert not square_arrival(result(arrival_angle_rad=0.8))


def test_tail_first_fast_spinning_or_very_fast_releases_are_penalised():
    from darts.sweep import release_penalty

    assert release_penalty(result(release_misalign_rad=0.3, release_spin_rad_s=10)) == 0
    assert release_penalty(result(release_misalign_rad=3.0)) > 0.2  # tail-first
    assert release_penalty(result(release_spin_rad_s=55)) > 0.2
    assert release_penalty(result(release_speed_m_s=9.4)) > 0.5


def test_a_release_past_the_lean_is_penalised():
    from darts.sweep import release_penalty

    assert release_penalty(result(release_x_m=0.3)) == 0
    assert release_penalty(result(release_x_m=0.6)) > 0.1
    assert release_penalty(result(release_x_m=0.3), lean_m=0.2) > 0.05


def test_the_wide_variant_set_covers_every_aero_corner_with_all_three_jitters():
    from darts.sweep import WIDE_VARIANTS

    assert len(WIDE_VARIANTS) == 18
    assert len({v[:3] for v in WIDE_VARIANTS}) == 18
    assert {v[3] for v in WIDE_VARIANTS} == {-0.01, 0.0, 0.01}
