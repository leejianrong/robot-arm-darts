#!/usr/bin/env bash
# Runs ON the pod, piped in by pod_train.sh. Clone, install, smoke-test, train, then publish the run
# directory over the runpodctl relay on success AND failure. Narrates itself: stage markers, a 60 s
# heartbeat with WARN lines, a timeout on every long step, and the metrics echoed into the log.
# Expects REF, RUN_ID, STEPS, SEED, NENVS, REPO in the env; WORK is the scratch dir (/work on a pod).
set -u
WORK=${WORK:-/work}
RUN=$WORK/runs/$RUN_ID
mkdir -p "$RUN"
JOBLOG=$WORK/job.log
exec > >(tee -a "$JOBLOG") 2>&1
STAGEFILE=$WORK/stage  # a file, so the heartbeat subshell sees the current stage
stage() { echo "$1" > "$STAGEFILE"; echo "STAGE $1"; }
stage boot

heartbeat() {  # stage, load, RAM and disk use, and how long the job log has been quiet
  local last now size quiet=0 changed
  changed=$(date +%s); size=0
  while true; do
    sleep "${HEARTBEAT_SECS:-60}"
    now=$(date +%s)
    [ "$(wc -c < "$JOBLOG")" != "$size" ] && { size=$(wc -c < "$JOBLOG"); changed=$now; }
    quiet=$((now - changed))
    ram=$(free | awk '/Mem:/ {printf "%d", $3*100/$2}')
    disk=$(df "$WORK" | awk 'NR==2 {gsub("%",""); print $5}')
    echo "HEARTBEAT stage=$(cat "$STAGEFILE") load=$(cut -d' ' -f1 /proc/loadavg) ram=${ram}% disk=${disk}% quiet=${quiet}s"
    [ "$quiet" -gt 600 ] && echo "WARN no output for ${quiet}s in stage $(cat "$STAGEFILE")"
    [ "$ram" -gt 90 ] && echo "WARN RAM at ${ram}%"
    [ "$disk" -gt 90 ] && echo "WARN disk at ${disk}%"
  done
}

publish() {
  echo "STAGE publish (was: $(cat "$STAGEFILE"))"
  cp "$JOBLOG" "$RUN/job.log" 2>/dev/null
  if [ -f "$RUN/metrics.json" ]; then  # numbers in the pod log survive a failed relay
    echo "RP_REPORT_BEGIN"; python3 -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1]))))" "$RUN/metrics.json"; echo "RP_REPORT_END"
  fi
  tar cf "$WORK/run.tar" -C "$WORK/runs" "$RUN_ID"
  BASE=darts-$RANDOM
  runpodctl send --code "$BASE" "$WORK/run.tar" > "$WORK/send.log" 2>&1 &
  SEND=$!
  sleep 5
  echo "RP_ARTIFACT_CODE=$(grep -oE "${BASE}[-0-9]+" "$WORK/send.log" | head -1)"
  wait "$SEND"  # holds the relay room until the laptop has received it (or the pod is reaped)
  pkill -P "$HEARTBEAT" 2>/dev/null; kill "$HEARTBEAT" 2>/dev/null || true
}

trap 'echo "STAGE failed (line $LINENO, was: $(cat "$STAGEFILE"))"; publish; exit 1' ERR
heartbeat &
HEARTBEAT=$!

# step <name> <timeout secs> <cmd...>: a hung step ends after its timeout instead of the pod lifetime
step() {
  local name=$1 secs=$2; shift 2
  stage "$name"
  timeout "$secs" "$@"
  local rc=$?
  [ "$rc" -eq 0 ] || { echo "ERROR step $name exited $rc (124 means timed out)"; return "$rc"; }
}

command -v uv >/dev/null || step pip 300 pip install -q uv
step clone 300 git clone -q "$REPO" "$WORK/src"
cd "$WORK/src" && git checkout -q "$REF"
JOB=${JOB:-train}
step install 900 uv sync -q $([ "$JOB" = train ] && echo --extra train)
step assets 600 make assets
set +e
case "$JOB" in
train)
  if [ "$STEPS" -gt 10000 ]; then  # the real code path on a tiny input before the long step
    step smoke 600 uv run darts train --steps 128 --n-envs 2 --seed "$SEED" --out "$WORK/smoke" || true
  fi
  step train 5400 uv run darts train --steps "$STEPS" --n-envs "$NENVS" --seed "$SEED" --scale "${SCALE:-0.25}" --n-steps "${N_STEPS:-64}" --batch-size "${BATCH_SIZE:-256}" --eval-every "${EVAL_EVERY:-10000}" --max-seconds 5000 --out "$RUN" ;;
basemap)
  step smoke 600 uv run darts basemap --targets 4 --budget 8 --rounds 1 --workers 2 --out "$WORK/smoke" || true
  step basemap 5400 uv run darts basemap --targets "${BASEMAP_TARGETS:-80}" --budget "${BASEMAP_BUDGET:-4000}" --rounds 2 --workers "$NENVS" --seed "$SEED" --max-seconds 4500 --out "$RUN" ;;
reach)  # how fast must the joints be to hit a board at REACH_DIST? one scripted search per speed
  pids=""
  for v in $REACH_SPEEDS; do
    uv run python -c "
import yaml; t = yaml.safe_load(open('twin.yaml'))
t['board']['distance_m'] = $REACH_DIST; t['servo']['velocity_limit_rad_s'] = $v
yaml.safe_dump(t, open('$WORK/twin_$v.yaml', 'w'))"
    (timeout 3000 uv run darts throw --scripted --no-video --seed "$SEED" --maxiter 60 --popsize 20 --twin "$WORK/twin_$v.yaml" --out "$RUN/v$v" > "$WORK/reach_$v.log" 2>&1
     echo "RESULT speed=$v rad/s dist=$REACH_DIST: $(grep -E 'best throw|hits the board' "$WORK/reach_$v.log" | tr '\n' ' ')") &
    pids="$pids $!"
  done
  stage reach; wait $pids ;;
esac
echo "$JOB exit code $?"
set -e
stage done
publish
