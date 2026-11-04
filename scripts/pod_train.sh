#!/usr/bin/env bash
# Train on a RunPod pod and pull the run directory back. The pod kills itself on a max-lifetime and
# idle watchdog (scripts/rp), and this script terminates it on every exit path and checks it is gone.
#
#   RUNPOD_API_KEY=... ./scripts/pod_train.sh        (key from the environment only; never printed)
#
# Knobs (env): STEPS SEED RUN_ID GIT_REF RP_MAX_HOURLY_USD RP_MAX_LIFETIME_SECS RP_VCPU_COUNT
set -euo pipefail
cd "$(dirname "$0")/.."
: "${RUNPOD_API_KEY:?set RUNPOD_API_KEY in the environment}"

export RUN_ID="${RUN_ID:-v4-$(date +%Y%m%d-%H%M%S)}"
export REF="${GIT_REF:-$(git rev-parse HEAD)}"
export STEPS="${STEPS:-200000}" SEED="${SEED:-0}"
export REPO="${REPO:-https://github.com/leejianrong/robot-arm-darts}"
git branch -r --contains "$REF" | grep -q . || { echo "commit $REF is not pushed; push it first" >&2; exit 1; }

export RP_POD_NAME="darts-$RUN_ID"
export RP_POD_IMAGE="${RP_POD_IMAGE:-python:3.12}"
export RP_COMPUTE_TYPE=CPU RP_VCPU_COUNT="${RP_VCPU_COUNT:-16}"
export RP_MAX_HOURLY_USD="${RP_MAX_HOURLY_USD:?set RP_MAX_HOURLY_USD (the most you will pay per hour)}"
export RP_MAX_LIFETIME_SECS="${RP_MAX_LIFETIME_SECS:-7200}"
export RP_STATE_FILE="runs/.rp-state-$RUN_ID"
job="$(base64 -w0 scripts/pod_job.sh)"
export RP_JOB_CMD="export REF=$REF RUN_ID=$RUN_ID STEPS=$STEPS SEED=$SEED REPO=$REPO OMP_NUM_THREADS=1; echo $job | base64 -d | bash"

trap './scripts/rp down' EXIT INT TERM
./scripts/rp up
./scripts/rp relay-get "runs/.incoming-$RUN_ID"
tar xf "runs/.incoming-$RUN_ID"/run.tar -C runs
rm -rf "runs/.incoming-$RUN_ID"
echo "run directory: runs/$RUN_ID"
