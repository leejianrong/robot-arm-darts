import dataclasses

import mujoco
import numpy as np
import pytest

from darts.sim import SCENE, ThrowParams, ThrowSim, assets_available, build_model
from darts.twin import load_twin

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not assets_available(), reason="run `make assets`"),
]

HOLD = (-1.0, 1.0, 0.0)  # the dart pose is fixed across tests


@pytest.fixture(scope="module")
def twin():
    return load_twin()


@pytest.fixture(scope="module")
def twin_1m(twin):
    """The flight tests use round numbers: a board 1 m away on a 1.2 m mount, whatever twin.yaml
    says (their launch point sits clear of the arm only at that height)."""
    return dataclasses.replace(
        twin,
        board=dataclasses.replace(twin.board, distance_m=1.0),
        mount=dataclasses.replace(twin.mount, height_m=1.2),
    )


def test_scene_path_exists():
    assert SCENE.exists()


def _rel_to_gripper(sim):
    rot = sim.data.xmat[sim._gripper_body].reshape(3, 3)
    return rot.T @ (sim.dart_state()[0] - sim.data.xpos[sim._gripper_body])


def test_dart_stays_gripped_at_rest(twin):
    sim = ThrowSim(twin)
    sim.reset(HOLD, settle_s=0.5)
    before = _rel_to_gripper(sim)
    for _ in range(round(2.0 / sim.model.opt.timestep)):
        sim._slew("gripper", twin.release.jaw_hold_rad)
        mujoco.mj_step(sim.model, sim.data)
    assert sim.dart_contacts()[0]
    assert np.linalg.norm(_rel_to_gripper(sim) - before) < 1e-3


def test_dart_survives_hard_swing_without_release_command(twin):
    """Friction alone must hold the dart through a fast motion until the jaw opens. The cross grip
    pinches at the jaw tips and creeps out after about 0.45 s, so the release comes before that."""
    sim = ThrowSim(twin)
    r = sim.throw(ThrowParams((-1.4, -1.5, -1.5), (0.0, 1.0, 1.3), 0.4), max_time_s=0.05)
    assert not r.slipped_early


def test_zero_velocity_limit_never_releases(twin):
    t = dataclasses.replace(twin, servo=dataclasses.replace(twin.servo, velocity_limit_rad_s=0.0))
    sim = ThrowSim(t)
    r = sim.throw(ThrowParams(HOLD, (-0.2, 0.5, -0.5), 0.1), max_time_s=1.0)
    assert not r.released


def test_jaw_opens_at_requested_step(twin):
    sim = ThrowSim(twin)
    p = ThrowParams(HOLD, HOLD, 0.2)
    sim.reset(p.q_start)
    dt = sim.model.opt.timestep
    gripper = sim._aid["gripper"]
    held_cmd = sim.data.ctrl[gripper]
    steps = 0
    while sim.data.ctrl[gripper] <= held_cmd + 1e-9 and steps < 2000:
        if steps * dt >= p.t_release_s:
            sim._slew("gripper", twin.release.jaw_open_rad)
        steps += 1
        mujoco.mj_step(sim.model, sim.data)
    assert steps * dt == pytest.approx(p.t_release_s, abs=2 * dt)


def test_dart_leaves_after_jaw_opens_with_release_speed(twin):
    sim = ThrowSim(twin)
    r = sim.throw(ThrowParams((-1.4, -1.5, -1.5), (0.0, 1.0, 1.3), 0.2))
    assert r.released and not r.slipped_early
    assert 1.0 < r.release_speed_m_s < 6.0


def test_free_flight_matches_closed_form(twin_1m):
    """Dart clear of the arm follows the ballistic arc to within 1 mm (RK4 integrator)."""
    model = build_model(twin_1m)
    model.opt.integrator = mujoco.mjtIntegrator.mjINT_RK4
    model.opt.timestep = 0.001
    sim = ThrowSim(twin_1m, model)
    sim.reset(HOLD, settle_s=0.1)
    a, v = sim._dart_qadr, sim._dart_vadr
    p0 = np.array([0.5, 0.0, 1.6])
    v0 = np.array([1.0, 0.0, 2.5])  # stays clear of the board
    sim.data.qpos[a : a + 3] = p0
    sim.data.qvel[v : v + 6] = 0
    sim.data.qvel[v : v + 3] = v0
    g, t_end = twin_1m.sim.gravity_m_s2, 0.4
    for _ in range(round(t_end / model.opt.timestep)):
        mujoco.mj_step(model, sim.data)
    expected = p0 + v0 * t_end + np.array([0, 0, -0.5 * g * t_end**2])
    assert np.linalg.norm(sim.data.qpos[a : a + 3] - expected) < 1e-3


def _launch(sim, speed, angle_deg, **kw):
    a = np.radians(angle_deg)
    return sim.launch((0.3, 0.0, 1.6), (speed * np.cos(a), 0.0, speed * np.sin(a)), **kw)


def _no_aero(twin):
    return dataclasses.replace(
        twin, aero=dataclasses.replace(twin.aero, drag_kg_m=0.0, fin_torque_nm=0.0)
    )


def test_launch_at_treble_20_sticks_and_scores_60(twin_1m):
    r = _launch(ThrowSim(twin_1m), 5.0, 25.7)
    assert r.stuck and r.score == 60


def test_launch_too_slow_falls_short_and_scores_zero(twin_1m):
    r = _launch(ThrowSim(twin_1m), 0.8, 10.0)
    assert not r.stuck and r.score == 0 and r.shortfall_m > 0


def test_drag_shortens_the_flight(twin_1m):
    off = _launch(ThrowSim(_no_aero(twin_1m)), 5.0, 25.7)
    on = _launch(ThrowSim(twin_1m), 5.0, 25.7)
    assert on.board_yz[1] < off.board_yz[1] - 0.001  # lands lower by more than 1 mm


def test_grazing_dart_bounces_and_square_dart_sticks(twin_1m):
    sim = ThrowSim(twin_1m)
    assert _launch(sim, 5.0, 17.6).stuck  # near-normal arrival
    a = np.radians(20.0)  # from close in, so it reaches the board slowly
    slow = sim.launch((0.9, 0.0, 1.6), (1.5 * np.cos(a), 0.0, 1.5 * np.sin(a)))
    assert slow.hit_board and not slow.stuck  # arrives too slowly to stick


def test_a_stuck_dart_stays_put_while_the_replay_keeps_recording(twin):
    import json
    from pathlib import Path

    best = json.loads((Path(__file__).parents[1] / "docs/baselines/best_throw.json").read_text())
    sim, tips = ThrowSim(twin), []
    # Sticking is knife-edge in the release, so look a few release times around the best throw.
    for dt in (0.0, 0.002, -0.002, 0.004, -0.004, 0.006, -0.006):
        p = ThrowParams(tuple(best["q_start"]), tuple(best["q_end"]), best["t_release_s"] + dt)
        if sim.throw(p).stuck:
            break

    def render():
        tips.append(sim.dart_state()[0].copy())
        return np.zeros((1, 1, 3))

    r = sim.throw(p, frames=[], render=render, fps=60)
    assert r.stuck, "no nearby release time sticks; re-run `darts throw --scripted`"
    hold = tips[-30:]  # the last half second of recording is all hold
    assert max(np.linalg.norm(t - hold[0]) for t in hold) < 1e-9


def test_spin_damping_is_stable_at_the_timestep(twin):
    """Explicit damping blows up when c*dt/I nears 2 (it did at 1.64 on the dart's thin axis)."""
    inertia = build_model(twin).body_inertia[build_model(twin).body("dart").id]
    assert twin.aero.spin_damping_nm_s * twin.sim.timestep_s / inertia.min() < 0.5


def test_cross_grip_releases_the_dart_along_its_direction_of_travel(twin):
    """Wrist roll puts the dart axis in the swing plane, so a fast throw never releases it sideways
    (the finger-axis grip released it 90-95 degrees off)."""
    p = ThrowParams((1.04, 0.36, 0.98), (-0.40, -0.95, -1.30), 0.168)
    r = ThrowSim(twin).throw(p)
    assert r.released and not r.slipped_early
    assert abs(np.sin(r.release_misalign_rad)) < 0.35


def test_the_hand_throw_sticks_in_most_aero_and_timing_variants(twin):
    """The baseline throw must not be knife-edge: the training-readiness gate."""
    from darts.policies import _BEST
    from darts.robust import robustness

    assert robustness(twin, _BEST)["stuck_rate"] >= 0.8


def test_training_logs_progress_and_stops_on_its_time_budget(twin, tmp_path, monkeypatch):
    """A pod run shows learning as it goes and still saves its policy when a rule stops it."""
    import json

    pytest.importorskip("stable_baselines3")
    import darts.train as t

    monkeypatch.setattr(t, "PROGRESS_SEEDS", [10_000, 10_001])
    monkeypatch.setattr(t, "HELD_OUT_SEEDS", [10_000, 10_001])
    monkeypatch.setattr(t, "REGRESSION", 2.0)  # two seeds are too noisy for the regression rule
    m = t.train(twin, 4096, 1, 0, 0.25, tmp_path, eval_every=1, max_seconds=0.0)
    rows = [json.loads(line) for line in (tmp_path / "metrics.jsonl").read_text().splitlines()]
    assert rows and {"steps", "on_board", "diverged_rate", "hand_on_board"} <= rows[0].keys()
    assert (tmp_path / "checkpoint.zip").exists() and (tmp_path / "policy.zip").exists()
    assert m["aborted"] == "time budget 0s used" and (tmp_path / "abort.txt").exists()
    assert len(m["aero_corners"]) == 2


def test_robustness_misses_are_measured_from_the_target(twin):
    from darts.policies import _BEST
    from darts.robust import robustness

    near = robustness(twin, _BEST)["median_miss_m"]
    shifted = robustness(twin, _BEST, target_yz=(0.0, 0.5))["median_miss_m"]
    assert shifted > near + 0.3


def test_torque_that_falls_with_speed_gives_a_slower_release(twin):
    """A servo with the same stall torque but a finite no-load speed throws slower."""
    from darts.policies import _BEST

    strong = dataclasses.replace(
        twin.servo, torque_limit_nm=6.0, velocity_limit_rad_s=9.0, no_load_speed_rad_s=0.0
    )
    flat = ThrowSim(dataclasses.replace(twin, servo=strong)).throw(_BEST)
    curved = dataclasses.replace(strong, no_load_speed_rad_s=9.0)
    real = ThrowSim(dataclasses.replace(twin, servo=curved)).throw(_BEST)
    assert real.release_speed_m_s < flat.release_speed_m_s - 0.5


def test_power_joints_add_mass_and_raise_the_release_speed(twin):
    from darts.policies import _BEST

    pw = dataclasses.replace(
        twin.power, torque_limit_nm=9.0, no_load_speed_rad_s=33.5, velocity_limit_rad_s=33.5
    )
    strong = dataclasses.replace(twin, power=pw)
    assert (
        ThrowSim(strong).throw(_BEST).release_speed_m_s
        > ThrowSim(twin).throw(_BEST).release_speed_m_s + 1
    )
    heavy = dataclasses.replace(strong, power=dataclasses.replace(pw, elbow_mass_kg=0.4))
    upper = build_model(twin).body("upper_arm").id
    assert build_model(heavy).body_mass[upper] == pytest.approx(
        build_model(twin).body_mass[upper] + 0.4
    )


def test_a_marker_renders_where_the_camera_projection_says(twin):
    """The mast camera's image agrees with the pinhole maths to half a pixel."""
    import os

    from darts.camera import project

    os.environ.setdefault("MUJOCO_GL", "osmesa")
    dart = dataclasses.replace(twin.dart, length_m=0.02, radius_m=0.03)  # a near-sphere marker
    t = dataclasses.replace(twin, dart=dart)
    sim = ThrowSim(t)
    point = np.array([0.35, 0.05, 1.75])
    a = sim._dart_qadr
    sim.data.qpos[a : a + 3] = point
    mujoco.mj_forward(sim.model, sim.data)
    try:
        renderer = mujoco.Renderer(sim.model, int(t.camera.height_px), int(t.camera.width_px))
    except Exception as e:  # no GL backend here
        pytest.skip(f"no GL backend: {e}")
    renderer.enable_segmentation_rendering()
    renderer.update_scene(sim.data, camera="board_cam")
    seg = renderer.render()
    hit = seg[..., 0] == sim.model.geom("dart_barrel").id
    renderer.close()
    assert hit.sum() > 50
    rows, cols = np.nonzero(hit)
    u, v = project(t, point)
    assert (cols.mean() + 0.5, rows.mean() + 0.5) == pytest.approx((u, v), abs=0.5)
