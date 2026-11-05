"""The pod-side job script must publish its run directory even when the job fails."""

import contextlib
import json
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
        "NENVS": "1",
        "HEARTBEAT_SECS": "1",
    }
    r = subprocess.run(
        ["bash", str(ROOT / "scripts/pod_job.sh")], env=env, capture_output=True, text=True,
        timeout=120,
    )  # fmt: skip
    assert r.returncode == 1
    assert "STAGE failed" in r.stdout and "was: clone" in r.stdout
    assert re.search(r"RP_ARTIFACT_CODE=darts-\d+-7-7", r.stdout)
    assert (inbox / "run.tar").exists()
    assert "HEARTBEAT stage=" in r.stdout and "ram=" in r.stdout


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


def test_spend_guard_deletes_only_my_pod_once_over_the_cap(tmp_path):
    run = {"uptimeSeconds": 3600, "desiredStatus": "RUNNING"}
    pods = [
        {"id": "mine", "name": "darts-t", "costPerHr": 3.6, **run},
        {"id": "theirs", "name": "other-job", "costPerHr": 9.0, **run},
        {"id": "gone", "name": "darts-old", "costPerHr": 0.3, "desiredStatus": "EXITED"},
    ]  # an exited pod has no uptimeSeconds
    (tmp_path / "pods.json").write_text(json.dumps(pods))
    shim = tmp_path / "runpodctl"
    shim.write_text(
        f'#!/bin/sh\ncase "$1 $2" in\n'
        f'"user ") echo \'{{"clientBalance": 50, "currentSpendPerHr": 12.6}}\';;\n'
        f'"pod list") cat {tmp_path}/pods.json;;\n'
        f'"pod delete") echo "$3" >> {tmp_path}/deleted;;\nesac\n'
    )
    shim.chmod(0o755)
    env = os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}"}
    guard = [str(ROOT / "scripts/rp_guard.py"), "--cap-usd", "2", "--interval", "1"]
    with contextlib.suppress(subprocess.TimeoutExpired):  # the guard loops until stopped
        subprocess.run(guard, env=env, capture_output=True, text=True, timeout=4)
    assert set((tmp_path / "deleted").read_text().split()) == {"mine", "gone"}  # never "theirs"
