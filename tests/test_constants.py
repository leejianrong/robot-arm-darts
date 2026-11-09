"""twin.yaml is the only source of calibratable numbers (ADR-0006): no code copy of one."""

import ast
import math
from pathlib import Path

import yaml

SRC = Path("src/darts")
PHYSICAL = ("sim", "servo", "power", "dart", "aero", "release", "board", "mount", "camera")

# A literal that equals a twin value only by coincidence: (file, value) -> why it is not a copy.
COINCIDENCES = {
    ("basemap.py", 0.9): "fraction of the board radius the targets cover",
    ("evaluate.py", 0.9): "Q13 on-board rate, not an angle",
    ("render.py", 0.9): "close-up camera distance, m",
    ("room.py", 0.9): "red of an RGBA colour",
    ("sim.py", 0.9): "red of an RGBA colour",
    ("room.py", 0.17): "stool radius and leg half-length, m",
    ("board.py", 0.17): "regulation double-ring radius, the texture's own scale",
    ("board.py", 60.0): "a texture parameter",
    ("render.py", 60.0): "free camera field of view for the room view",
    ("sweep.py", 60.0): "differential-evolution iteration count",
    ("render.py", 480.0): "video frame height (the mast camera's own size comes from the twin)",
    ("render.py", 640.0): "video frame width",
    ("detect.py", 0.6): "lower bound of the accepted ellipse-axis range",
    ("cli.py", 60.0): "search iteration count default",
    ("ladder.py", 60.0): "search iteration count default",
    ("cli.py", 1.4): "a rung of the distance ladder, m, not the mount height",
    ("ladder.py", 4.5): "lower edge of the human release-speed band, m/s, not a servo limit",
}


def _is_round(v: float) -> bool:
    """1, 2 or 5 times a power of ten: too ordinary a number to call a copy."""
    return round(abs(v) / 10 ** math.floor(math.log10(abs(v))), 6) in (1.0, 2.0, 5.0)


def twin_values() -> dict[float, list[str]]:
    twin = yaml.safe_load(Path("twin.yaml").read_text())
    out: dict[float, list[str]] = {}
    for section in PHYSICAL:
        for key, v in twin[section].items():
            if v and not _is_round(float(v)):
                out.setdefault(float(v), []).append(f"{section}.{key}")
    return out


def duplicates(source: str, name: str, values: dict[float, list[str]]) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Constant) or isinstance(node.value, bool):
            continue
        if not isinstance(node.value, int | float):
            continue
        v = float(node.value)
        if v in values and (name, v) not in COINCIDENCES:
            found.append(f"{name}:{node.lineno} {node.value} = {values[v]}")
    return found


def test_no_source_file_repeats_a_twin_number():
    values = twin_values()
    found = [d for f in sorted(SRC.glob("*.py")) for d in duplicates(f.read_text(), f.name, values)]
    assert not found, "a twin.yaml number is hard-coded (read it from the twin):\n" + "\n".join(
        found
    )


def test_the_guard_catches_a_duplicate():
    values = twin_values()
    assert duplicates("KP = 998.22\n", "new.py", values)  # servo.kp
    assert duplicates("g = 9.81\n", "new.py", values)  # sim.gravity_m_s2
    assert not duplicates("x = 3.14159\n", "new.py", values)
