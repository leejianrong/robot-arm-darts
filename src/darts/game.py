"""501 with double-out: three darts a turn, bust restores the turn's starting score."""

from dataclasses import dataclass, field

from darts.board import Hit

START_SCORE = 501
MAX_TURNS = 40  # a game that has not finished by then is called off


@dataclass
class Game:
    remaining: int = START_SCORE
    finished: bool = False
    darts_in_turn: int = 0
    turns: int = 0  # turns completed
    turn_start: int = field(init=False)

    def __post_init__(self) -> None:
        self.turn_start = self.remaining

    @property
    def over(self) -> bool:
        return self.finished or self.turns >= MAX_TURNS

    def throw(self, hit: Hit) -> str:
        """Apply one dart. Returns "ok", "bust" or "checkout"."""
        if self.over:
            raise ValueError("game is over")
        left = self.remaining - hit.points
        is_double = hit.ring in ("double", "bull")
        if left < 0 or left == 1 or (left == 0 and not is_double):
            self.remaining = self.turn_start
            self._end_turn()
            return "bust"
        self.remaining = left
        if left == 0:
            self.finished = True
            return "checkout"
        self.darts_in_turn += 1
        if self.darts_in_turn == 3:
            self._end_turn()
        return "ok"

    def _end_turn(self) -> None:
        self.darts_in_turn = 0
        self.turns += 1
        self.turn_start = self.remaining
