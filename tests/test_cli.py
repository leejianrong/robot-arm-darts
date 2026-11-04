import json

import pytest

from darts.cli import main
from darts.sim import assets_available


def test_help_exits_cleanly(capsys):
    try:
        main(["--help"])
    except SystemExit as e:
        assert e.code == 0
    assert "darts" in capsys.readouterr().out


@pytest.mark.integration
@pytest.mark.skipif(not assets_available(), reason="run `make assets`")
def test_eval_prints_json_and_exits_nonzero_when_the_target_is_missed(capsys):
    code = main(["eval", "--policy", "random", "--n", "5"])
    out = json.loads(capsys.readouterr().out)
    assert out["n"] == 5 and out["policy"] == "random"
    assert code == 1 and out["meets_q13"] is False
