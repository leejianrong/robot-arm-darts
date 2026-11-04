"""The policy's contract: a fixed state going in, a small throw action coming out (ADR-0003/4)."""

from dataclasses import dataclass

import numpy as np

from darts.sim import ThrowParams
from darts.sweep import LIMITS, T_RELEASE
from darts.twin import Twin

JOINT_COUNT = 6  # five arm joints and the gripper
PAN_LIMIT_RAD = 0.3  # enough to cover the board width at 1 m
ACTION_DIM = 8  # start (3), end (3), release time, pan
STATE_DIM = 12
BOARD_NORMAL = (-1.0, 0.0, 0.0)  # points from the board towards the thrower
REST_JOINTS = (0.0,) * JOINT_COUNT  # the arm's pose when the episode starts

_LOW = np.array([LIMITS[j][0] for j in LIMITS] * 2 + [T_RELEASE[0], -PAN_LIMIT_RAD])
_HIGH = np.array([LIMITS[j][1] for j in LIMITS] * 2 + [T_RELEASE[1], PAN_LIMIT_RAD])


@dataclass(frozen=True)
class State:
    target_in_base: np.ndarray  # (3,) aim point on the board face, metres in the arm base frame
    board_normal_in_base: np.ndarray  # (3,) unit vector
    joint_pos: np.ndarray  # (6,) encoder readings, radians

    def to_array(self) -> np.ndarray:
        return np.concatenate([self.target_in_base, self.board_normal_in_base, self.joint_pos])

    @classmethod
    def from_array(cls, a: np.ndarray) -> "State":
        if a.shape != (STATE_DIM,):
            raise ValueError(f"state needs shape ({STATE_DIM},), got {a.shape}")
        return cls(a[:3].copy(), a[3:6].copy(), a[6:].copy())


def target_state(twin: Twin, y: float, z: float) -> State:
    """State for a target at lateral offset `y` and height `z` above the board centre."""
    height = twin.board.centre_height_m - twin.mount.height_m + z
    return State(
        np.array([twin.board.distance_m, y, height]),
        np.array(BOARD_NORMAL),
        np.array(REST_JOINTS),
    )


def decode_action(action: np.ndarray) -> tuple[ThrowParams, bool]:
    """Map an action in [-1, 1]^8 to throw parameters. Returns (params, clipped)."""
    if action.shape != (ACTION_DIM,):
        raise ValueError(f"action needs shape ({ACTION_DIM},), got {action.shape}")
    clipped = bool(np.any(np.abs(action) > 1.0))
    x = _LOW + (np.clip(action, -1.0, 1.0) + 1.0) / 2.0 * (_HIGH - _LOW)
    return ThrowParams(tuple(x[:3]), tuple(x[3:6]), float(x[6]), float(x[7])), clipped


def encode_action(p: ThrowParams) -> np.ndarray:
    """Inverse of `decode_action`."""
    x = np.array([*p.q_start, *p.q_end, p.t_release_s, p.pan_rad])
    return 2.0 * (x - _LOW) / (_HIGH - _LOW) - 1.0
