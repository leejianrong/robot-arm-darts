from pathlib import Path

import pytest
import yaml

from darts.twin import TwinConfigError, load_twin, parse_twin

ROOT = Path(__file__).resolve().parent.parent


def raw():
    return yaml.safe_load((ROOT / "twin.yaml").read_text())


def test_repo_twin_loads():
    t = load_twin(ROOT / "twin.yaml")
    assert t.dart.mass_kg == pytest.approx(0.010)
    assert t.board.distance_m == pytest.approx(1.0)
    assert t.board.centre_height_m == pytest.approx(1.73)


def test_unknown_key_rejected():
    r = raw()
    r["servo"]["mystery"] = 1.0
    with pytest.raises(TwinConfigError, match="unknown keys"):
        parse_twin(r)


def test_missing_key_rejected():
    r = raw()
    del r["servo"]["kp"]
    with pytest.raises(TwinConfigError, match="missing keys"):
        parse_twin(r)


def test_unknown_section_rejected():
    r = raw()
    r["extra"] = {}
    with pytest.raises(TwinConfigError, match="unknown top-level"):
        parse_twin(r)


def test_wrong_schema_version_rejected():
    r = raw()
    r["schema_version"] = 99
    with pytest.raises(TwinConfigError, match="schema_version"):
        parse_twin(r)


def test_non_number_rejected():
    r = raw()
    r["servo"]["kp"] = "high"
    with pytest.raises(TwinConfigError, match="expected a number"):
        parse_twin(r)
