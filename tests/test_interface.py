import numpy as np
import pytest

from darts.interface import (
    ACTION_DIM,
    STATE_DIM,
    State,
    decode_action,
    encode_action,
    target_state,
)
from darts.twin import load_twin


def test_state_round_trips_through_an_array():
    s = target_state(load_twin(), 0.05, -0.02)
    a = s.to_array()
    assert a.shape == (STATE_DIM,)
    back = State.from_array(a)
    for field in ("target_in_base", "board_normal_in_base", "joint_pos"):
        np.testing.assert_array_equal(getattr(back, field), getattr(s, field))


def test_state_rejects_a_wrong_shape():
    with pytest.raises(ValueError, match="shape"):
        State.from_array(np.zeros(5))


def test_target_is_in_the_base_frame():
    t = load_twin()
    s = target_state(t, 0.1, 0.0)
    assert s.target_in_base[0] == pytest.approx(t.board.distance_m)
    assert s.target_in_base[2] == pytest.approx(t.board.centre_height_m - t.mount.height_m)


def test_in_range_action_is_not_flagged():
    _, clipped = decode_action(np.zeros(ACTION_DIM))
    assert not clipped


def test_out_of_range_action_is_clipped_and_flagged():
    params, clipped = decode_action(np.full(ACTION_DIM, 5.0))
    assert clipped
    assert params.t_release_s == pytest.approx(decode_action(np.ones(ACTION_DIM))[0].t_release_s)


def test_encode_inverts_decode():
    a = np.linspace(-0.9, 0.9, ACTION_DIM)
    params, _ = decode_action(a)
    np.testing.assert_allclose(encode_action(params), a)
