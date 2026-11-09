from darts.ladder import band_flags, farthest_robust, parse_power


def row(**kw):
    return dict(release_speed_m_s=5.9, release_angle_deg=16.0, release_x_m=0.3, lean_m=0.4) | kw


def test_a_human_like_release_is_inside_every_band():
    assert band_flags(row()) == []


def test_a_fast_steep_far_reaching_release_is_flagged():
    assert band_flags(row(release_speed_m_s=9.4)) == ["speed"]
    assert band_flags(row(release_angle_deg=40)) == ["angle"]
    assert band_flags(row(release_x_m=0.6)) == ["lean"]


def test_power_spec_parses_in_the_pod_job_order():
    p = parse_power("9:33.5:0.38:0.4")
    assert (p.torque_limit_nm, p.no_load_speed_rad_s, p.velocity_limit_rad_s) == (9, 33.5, 33.5)
    assert (p.shoulder_mass_kg, p.elbow_mass_kg) == (0.38, 0.4)


def test_farthest_robust_ignores_the_sensitivity_lean_and_failed_rungs():
    rows = [
        dict(distance_m=1.0, lean_m=0.4, robust=True),
        dict(distance_m=1.8, lean_m=0.4, robust=True),
        dict(distance_m=2.37, lean_m=0.4, robust=False),
        dict(distance_m=2.37, lean_m=0.2, robust=True),
    ]
    assert farthest_robust(rows)["distance_m"] == 1.8
    assert farthest_robust([dict(distance_m=1.0, lean_m=0.4, robust=False)]) is None
