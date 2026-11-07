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
export GIT_TERMINAL_PROMPT=0  # a hung credential prompt once sat in this step for 16 minutes
step assets 240 timeout -s KILL 200 make assets || { rm -rf assets/menagerie; step assets_retry 240 timeout -s KILL 200 make assets; }
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
render)  # which GL backend works on this pod, and does it match the laptop? see scripts/gl_check.py
  (apt-get install -y -q libosmesa6 libegl1 libgl1 libglu1-mesa >/dev/null 2>&1 || echo "apt install failed")
  for gl in egl osmesa; do
    echo "RESULT $(MUJOCO_GL=$gl timeout 300 uv run python scripts/gl_check.py 2>&1 | tail -1 | cut -c1-400)"
  done
  echo "RESULT nvidia-smi: $(nvidia-smi -L 2>&1 | head -1)"
  step clip 900 env MUJOCO_GL=osmesa uv run darts replay --policy hand --seed 3 --out "$RUN/clip.mp4" ;;
reach)  # what servo does a board at REACH_DIST need? one scripted search per speed x torque
  pids=""
  for set in $REACH_POWER_SETS; do  # T:W:shoulder_kg:elbow_kg on shoulder_lift and elbow_flex, stock servo elsewhere
    IFS=: read -r T W MS ME <<< "$set"; tag=$(echo "$set" | tr ':' '_')
    uv run python -c "
import yaml; t = yaml.safe_load(open('twin.yaml'))
t['board']['distance_m'] = $REACH_DIST
t['power'] = dict(torque_limit_nm=$T, no_load_speed_rad_s=$W, velocity_limit_rad_s=$W, shoulder_mass_kg=$MS, elbow_mass_kg=$ME)
yaml.safe_dump(t, open('$WORK/twin_$tag.yaml', 'w'))"
    (timeout 3000 uv run darts throw --scripted --no-video --seed "$SEED" --maxiter 60 --popsize 20 --twin "$WORK/twin_$tag.yaml" --out "$RUN/p$tag" > "$WORK/reach_$tag.log" 2>&1
     echo "RESULT power=$set (T N.m:no-load rad/s:shoulder kg:elbow kg) dist=$REACH_DIST: $(grep -E 'best throw|hits the board' "$WORK/reach_$tag.log" | tr '\n' ' ')") &
    pids="$pids $!"
  done
  for v in ${REACH_SPEEDS:-}; do for q in $REACH_TORQUES; do
    uv run python -c "
import yaml; t = yaml.safe_load(open('twin.yaml'))
t['board']['distance_m'] = $REACH_DIST; t['servo']['velocity_limit_rad_s'] = $v; t['servo']['torque_limit_nm'] = $q
if '$REACH_DERATE' == '1': t['servo']['no_load_speed_rad_s'] = $v
yaml.safe_dump(t, open('$WORK/twin_${v}_$q.yaml', 'w'))"
    (timeout 3000 uv run darts throw --scripted --no-video --seed "$SEED" --maxiter 60 --popsize 20 --twin "$WORK/twin_${v}_$q.yaml" --out "$RUN/v${v}_q$q" > "$WORK/reach_${v}_$q.log" 2>&1
     echo "RESULT speed=$v rad/s torque=$q N.m dist=$REACH_DIST: $(grep -E 'best throw|hits the board' "$WORK/reach_${v}_$q.log" | tr '\n' ' ')") &
    pids="$pids $!"
  done; done
  stage reach; wait $pids ;;
esac
echo "$JOB exit code $?"
set -e
stage done
publish
