from darts.cli import main


def test_help_exits_cleanly(capsys):
    try:
        main(["--help"])
    except SystemExit as e:
        assert e.code == 0
    assert "darts" in capsys.readouterr().out
