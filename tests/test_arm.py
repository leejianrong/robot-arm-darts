import math

import numpy as np
import pytest

from darts.arm import LeRobotArm, SimArm, plan, read_log, run, write_log
from darts.env import DartThrowEnv
from darts.interface import decode_action
from darts.policies import hand_tuned_policy
from darts.sim import ARM_JOINTS, ThrowParams, ThrowSim, assets_available
from darts.twin import load_twin

needs_assets = pytest.mark.skipif(not assets_available(), reason="run `make assets`")


class FakeBackend:
    """Stands in for a LeRobot robot: remembers the last action and reports it back."""

    def __init__(self):
        self.actions: list[dict[str, float]] = []
        self.pos = {f"{n}.pos": 0.0 for n in (*ARM_JOINTS, "gripper")}

    def send_action(self, action):
        self.actions.append(dict(action))
        self.pos |= action

    def get_observation(self):
        return dict(self.pos)

    def wait(self, seconds):
        pass


PARAMS = ThrowParams((-1.0, 0.5, 0.0), (0.8, -0.4, 0.2), 0.3, 0.05)


def commands_only(log):
    return [(e["t"], e["name"], e["values"]) for e in log if e["kind"] == "command"]


def test_a_throw_plans_a_start_a_swing_and_a_release():
    cmds = plan(PARAMS)
    assert [(c.kind, c.t) for c in cmds] == [
        ("prepare", 0.0),
        ("set_targets", 0.0),
        ("open_gripper", 0.3),
    ]
    assert cmds[0].values == {
        "shoulder_lift": -1.0,
        "elbow_flex": 0.5,
        "wrist_flex": 0.0,
        "shoulder_pan": 0.05,
    }


def test_the_stub_sends_degrees_to_its_backend_and_reads_radians_back():
    backend = FakeBackend()
    arm = LeRobotArm(backend, gripper_open_rad=1.0)
    log = run(arm, plan(PARAMS))
    sent = backend.actions
    assert sent[1] == {"shoulder_lift.pos": pytest.approx(math.degrees(0.8)),
                       "elbow_flex.pos": pytest.approx(math.degrees(-0.4)),
                       "wrist_flex.pos": pytest.approx(math.degrees(0.2))}  # fmt: skip
    assert sent[-1] == {"gripper.pos": pytest.approx(math.degrees(1.0))}
    assert log[-1]["gripper_open"] is True
    assert log[-1]["joint_pos"][1] == pytest.approx(0.8)  # shoulder_lift read back in radians


def test_the_log_round_trips(tmp_path):
    log = run(LeRobotArm(FakeBackend(), 1.0), plan(PARAMS))
    write_log(log, tmp_path / "throw.jsonl")
    assert read_log(tmp_path / "throw.jsonl") == log


@pytest.mark.parametrize(
    "bad",
    [{"shoulder_lift": float("nan")}, {"elbow_flex": 9.0}, {"tail": 0.1}, {"wrist_flex": math.inf}],
)
def test_malformed_targets_are_rejected_before_anything_moves(bad):
    backend = FakeBackend()
    with pytest.raises(ValueError):
        LeRobotArm(backend, 1.0).set_targets(bad)
    assert backend.actions == []


@needs_assets
@pytest.mark.integration
def test_the_same_policy_gives_the_same_commands_through_the_sim_and_the_stub():
    twin = load_twin("twin.yaml")
    env = DartThrowEnv(twin)
    env.reset(seed=10_000)
    params, _ = decode_action(hand_tuned_policy(env.state(), np.random.default_rng(0)))
    sim_log = run(SimArm(ThrowSim(twin)), plan(params))
    stub_log = run(LeRobotArm(FakeBackend(), twin.release.jaw_open_rad), plan(params))
    assert commands_only(sim_log) == commands_only(stub_log)


@needs_assets
@pytest.mark.integration
def test_the_sim_arm_swings_towards_its_targets_and_opens_the_jaw():
    twin = load_twin("twin.yaml")
    arm = SimArm(ThrowSim(twin))
    log = run(arm, plan(PARAMS))
    first = next(e for e in log if e["kind"] == "state")
    last = log[-1]
    assert first["joint_pos"][1] == pytest.approx(-1.0, abs=0.05)  # shoulder_lift at the start pose
    assert last["joint_pos"][1] > first["joint_pos"][1] + 0.5  # swung towards 0.8
    assert last["gripper_open"] and last["joint_pos"][5] > 0.3  # the jaw moved open
    with pytest.raises(ValueError):
        arm.set_targets({"elbow_flex": 7.0})
