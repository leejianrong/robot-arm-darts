#!/usr/bin/env bash
# Train on a RunPod pod and pull the run directory back. The pod kills itself on a max-lifetime and
# idle watchdog (scripts/rp), and this script terminates it on every exit path and checks it is gone.
#
#   RUNPOD_API_KEY=... ./scripts/pod_train.sh        (key from the environment only; never printed)
#
# Knobs (env): JOB=train|basemap BASEMAP_TARGETS BASEMAP_BUDGET STEPS SEED EVAL_EVERY SCALE N_STEPS BATCH_SIZE RUN_ID GIT_REF RP_MAX_HOURLY_USD RP_MAX_LIFETIME_SECS RP_VCPU_COUNT
set -euo pipefail
cd "$(dirname "$0")/.."
: "${RUNPOD_API_KEY:?set RUNPOD_API_KEY in the environment}"

export RUN_ID="${RUN_ID:-${JOB:-train}-$(date +%Y%m%d-%H%M%S)}"
export REF="${GIT_REF:-$(git rev-parse HEAD)}"
export STEPS="${STEPS:-200000}" SEED="${SEED:-0}" EVAL_EVERY="${EVAL_EVERY:-10000}"
export JOB="${JOB:-train}" BASEMAP_TARGETS="${BASEMAP_TARGETS:-80}" BASEMAP_BUDGET="${BASEMAP_BUDGET:-4000}"
export SCALE="${SCALE:-0.25}" N_STEPS="${N_STEPS:-64}" BATCH_SIZE="${BATCH_SIZE:-256}"
export REPO="${REPO:-https://github.com/leejianrong/robot-arm-darts}"
git branch -r --contains "$REF" | grep -q . || { echo "commit $REF is not pushed; push it first" >&2; exit 1; }

export RP_POD_NAME="darts-$RUN_ID"
export RP_POD_IMAGE="${RP_POD_IMAGE:-python:3.12}"
export RP_COMPUTE_TYPE="${RP_COMPUTE_TYPE:-CPU}" RP_VCPU_COUNT="${RP_VCPU_COUNT:-16}"
export NENVS="${NENVS:-$RP_VCPU_COUNT}"  # nproc on a pod shows the host; a GPU pod needs NENVS set
export RP_MAX_HOURLY_USD="${RP_MAX_HOURLY_USD:?set RP_MAX_HOURLY_USD (the most you will pay per hour)}"
export RP_MAX_LIFETIME_SECS="${RP_MAX_LIFETIME_SECS:-7200}"
export RP_STATE_FILE="runs/.rp-state-$RUN_ID"
job="$(base64 -w0 scripts/pod_job.sh)"
export RP_JOB_CMD="export REF=$REF RUN_ID=$RUN_ID STEPS=$STEPS SEED=$SEED EVAL_EVERY=$EVAL_EVERY JOB=$JOB BASEMAP_TARGETS=$BASEMAP_TARGETS BASEMAP_BUDGET=$BASEMAP_BUDGET SCALE=$SCALE N_STEPS=$N_STEPS BATCH_SIZE=$BATCH_SIZE NENVS=$NENVS REPO=$REPO OMP_NUM_THREADS=1; echo $job | base64 -d | bash"

WATCH="runs/$RUN_ID.watch.log"  # raw snapshots of the pod log, kept even if the pod vanishes
mkdir -p runs
WATCHER=
trap 'kill $WATCHER 2>/dev/null; ./scripts/rp down' EXIT INT TERM
./scripts/rp up

# Boot check: the container must start producing output soon, or fail fast instead of billing silently.
booted=""
for i in $(seq 1 "${BOOT_CHECKS:-24}"); do  # 24 x 10 s = 4 minutes
  ./scripts/rp logs --tail 50 2>&1 | tee -a "$WATCH" | grep -q "STAGE" && { booted=1; break; }
  echo "waiting for the pod to boot ($i)..."; sleep 10
done
[ -n "$booted" ] || { echo "pod produced no output in 4 min; system log:" >&2; ./scripts/rp logs --source system --tail 50 >&2 || true; exit 1; }

# Watcher: every 60 s, save a snapshot and print the latest stage, heartbeat and any WARN/ERROR line.
( while true; do
    sleep 60
    snap="$(./scripts/rp logs --tail 200 2>&1 || true)"
    printf '%s\n--- %s\n' "$snap" "$(date -u +%FT%TZ)" >> "$WATCH"
    echo "$snap" | grep -E "STAGE|HEARTBEAT|WARN|ERROR|EVAL|ABORT|PROGRESS|RESULT" | tail -3
  done ) &
WATCHER=$!
./scripts/rp relay-get "runs/.incoming-$RUN_ID"
tar xf "runs/.incoming-$RUN_ID"/run.tar -C runs
rm -rf "runs/.incoming-$RUN_ID"
echo "run directory: runs/$RUN_ID"
