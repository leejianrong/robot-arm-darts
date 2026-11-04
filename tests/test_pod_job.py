"""The pod-side job script must publish its run directory even when the job fails."""

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fake_runpodctl(bin_dir: Path, inbox: Path) -> None:
    """`runpodctl send --code C file` prints a final code and keeps a copy, like the relay."""
    bin_dir.mkdir()
    shim = bin_dir / "runpodctl"
    shim.write_text(f'#!/bin/sh\ncp "$4" {inbox}/\necho "Code is: $3-7-7"\nsleep 1\n')
    shim.chmod(0o755)


def test_a_failing_job_still_publishes_its_artifact(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    fake_runpodctl(tmp_path / "bin", inbox)
    env = os.environ | {
        "PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}",
        "WORK": str(tmp_path / "work"),
        "REPO": str(ROOT),
        "REF": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",  # not a commit: the checkout fails
        "RUN_ID": "t",
        "STEPS": "1",
        "SEED": "0",
    }
    r = subprocess.run(
        ["bash", str(ROOT / "scripts/pod_job.sh")], env=env, capture_output=True, text=True,
        timeout=120,
    )  # fmt: skip
    assert r.returncode == 1
    assert "STAGE failed" in r.stdout and "was: install" in r.stdout
    assert re.search(r"RP_ARTIFACT_CODE=darts-\d+-7-7", r.stdout)
    assert (inbox / "run.tar").exists()


def test_pod_train_refuses_to_start_without_a_key_or_a_price_cap(tmp_path):
    base = {"PATH": os.environ["PATH"], "HOME": str(tmp_path)}
    no_key = subprocess.run(
        ["bash", str(ROOT / "scripts/pod_train.sh")], env=base, capture_output=True, text=True
    )
    assert no_key.returncode != 0 and "RUNPOD_API_KEY" in no_key.stderr
    no_cap = subprocess.run(
        ["bash", str(ROOT / "scripts/pod_train.sh")],
        env=base | {"RUNPOD_API_KEY": "x"},
        capture_output=True,
        text=True,
    )
    assert no_cap.returncode != 0
    assert "RP_MAX_HOURLY_USD" in no_cap.stderr or "not pushed" in no_cap.stderr
