#!/usr/bin/env bash
# Runs ON the pod, piped in by pod_train.sh. Clone, install, train, then publish the run directory
# over the runpodctl relay on success AND failure. Expects REF, RUN_ID, STEPS, SEED, REPO in the env;
# WORK is the scratch directory (/work on a pod).
set -u
WORK=${WORK:-/work}
RUN=$WORK/runs/$RUN_ID
mkdir -p "$RUN"
STAGE=boot
stage() { STAGE=$1; echo "STAGE $1"; }
publish() {
  echo "STAGE publish (was: $STAGE)"
  tar cf "$WORK/run.tar" -C "$WORK/runs" "$RUN_ID"
  BASE=darts-$RANDOM
  runpodctl send --code "$BASE" "$WORK/run.tar" > "$WORK/send.log" 2>&1 &
  SEND=$!
  sleep 5
  echo "RP_ARTIFACT_CODE=$(grep -oE "${BASE}[-0-9]+" "$WORK/send.log" | head -1)"
  wait "$SEND"  # holds the relay room until the laptop has received it (or the pod is reaped)
  pkill -P "$HEARTBEAT" 2>/dev/null; kill "$HEARTBEAT" 2>/dev/null || true
}
trap 'echo "STAGE failed (line $LINENO, was: $STAGE)"; publish; exit 1' ERR
( while true; do sleep 60; echo "heartbeat stage=$STAGE load=$(cut -d' ' -f1 /proc/loadavg)"; done ) &
HEARTBEAT=$!

stage install
command -v uv >/dev/null || pip install -q uv
git clone -q "$REPO" "$WORK/src" && cd "$WORK/src" && git checkout -q "$REF"
uv sync -q --extra train
make assets
stage train
set +e
timeout 5400 uv run darts train --steps "$STEPS" --n-envs "$(nproc)" --seed "$SEED" --out "$RUN"
echo "train exit code $?"
set -e
stage done
publish
