"""Where to aim next in 501 double-out (DART-26)."""

import math
from dataclasses import dataclass

from darts.board import DOUBLE_IN, DOUBLE_OUT, SEGMENTS, TREBLE_IN, TREBLE_OUT

SETUP_DOUBLE = 16  # leave 32: a double that still has a second try (D8) after a miss
BULL_FINISH = 50


@dataclass(frozen=True)
class Target:
    ring: str  # single, double, treble or bull
    segment: int | None = None  # None for the bull

    @property
    def points(self) -> int:
        if self.segment is None:
            return 50
        return self.segment * {"single": 1, "double": 2, "treble": 3}[self.ring]


TREBLE_20 = Target("treble", 20).points  # the most one dart can score outside the bull


def choose_target(remaining: int) -> Target:
    """The target for the next dart. Treble 20 while far from out, then a single that leaves a
    double, then the double. Never aims at a score that would bust the turn."""
    if remaining < 2:
        raise ValueError(f"cannot finish from {remaining}")
    if remaining == BULL_FINISH:
        return Target("bull")
    if remaining <= 40 and remaining % 2 == 0:
        return Target("double", remaining // 2)
    if remaining <= TREBLE_20:  # a single that leaves a double: D16 if it can, else the closest
        return Target("single", min(20, max(1, remaining - 2 * SETUP_DOUBLE)))
    # T20 unless it leaves exactly 1 (a bust), then T19
    return Target("treble", 19 if remaining - TREBLE_20 == 1 else 20)


def aim_point(target: Target) -> tuple[float, float]:
    """(y, z) offset from the board centre, metres, of the middle of the target's area."""
    if target.segment is None:
        return 0.0, 0.0
    r = {
        "single": (TREBLE_OUT + DOUBLE_IN) / 2,
        "treble": (TREBLE_IN + TREBLE_OUT) / 2,
        "double": (DOUBLE_IN + DOUBLE_OUT) / 2,
    }[target.ring]
    angle = math.radians(SEGMENTS.index(target.segment) * 18)  # clockwise from the top
    return -r * math.sin(angle), r * math.cos(angle)
