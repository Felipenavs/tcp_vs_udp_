#!/usr/bin/env bash
set -euo pipefail

#############################################
# CONFIG
#############################################
ILAB_USER=""  # <===== must set ilab username             
ILAB_PASS="${ILAB_PASS:-}"   # export ILAB_PASS='...' (recommended) or leave empty to prompt at runtime

SERVER_SSH_HOST="cd.cs.rutgers.edu"
CLIENT_SSH_HOST="cp.cs.rutgers.edu"

REMOTE_DIR="/common/home/${ILAB_USER}/tcp_udp_benchmark"

BIND="0.0.0.0"
PORT="9091"

# Delays to avoid iLab kicks for too many SSH sessions
DELAY=1
HEAVY_DELAY=3   

# Retry SSH hiccups
RETRIES=2
RETRY_SLEEP=8

#############################################
# Internals
#############################################
die() { echo "Error: $*" >&2; exit 1; }
need_cmd() { command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"; }

# Password-only SSH options
SSH_OPTS=(
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/dev/null
  -o LogLevel=ERROR

  -o PreferredAuthentications=password
  -o PasswordAuthentication=yes
  -o KbdInteractiveAuthentication=no
  -o ChallengeResponseAuthentication=no

  -o PubkeyAuthentication=no
  -o IdentitiesOnly=yes
  -o NumberOfPasswordPrompts=1

  -o GSSAPIAuthentication=no
  -o BatchMode=no
)

LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
LOGFILE="${LOCAL_DIR}/full_sweep_${TS}.log"
PULL_DIR="${LOCAL_DIR}/ilab_pull_fullsweep_${TS}"
SEEN_FILE="${LOCAL_DIR}/seen_runs_${TS}.txt"

prompt_pass_if_needed() {
  if [[ -z "$ILAB_PASS" ]]; then
    read -s -p "Enter iLab *CS password* for ${ILAB_USER}: " ILAB_PASS
    echo
  fi
  export SSHPASS="$ILAB_PASS"   
}

ssh_cmd() {
  local host="$1"; shift
  sshpass -e ssh "${SSH_OPTS[@]}" "${ILAB_USER}@${host}" "$@"
}

ssh_block() {
  local host="$1"; shift
  sshpass -e ssh "${SSH_OPTS[@]}" "${ILAB_USER}@${host}" "bash -s" <<EOF
set -euo pipefail
$*
EOF
}

ssh_test_login() {
  local host="$1"
  echo "==> Testing SSH password auth to ${host}" | tee -a "$LOGFILE"
  ssh_cmd "$host" "echo OK \$(whoami)@\$(hostname)" >/dev/null
}

ensure_remote_dirs() {
  local host="$1"
  ssh_block "$host" "mkdir -p '${REMOTE_DIR}' '${REMOTE_DIR}/results' '${REMOTE_DIR}/plots'"
}

rsync_push_once() {
  local host="$1"
  echo "==> Syncing project to ${host}:${REMOTE_DIR} (once)" | tee -a "$LOGFILE"
  ensure_remote_dirs "$host"
  sshpass -e rsync -az --delete \
    -e "ssh ${SSH_OPTS[*]}" \
    "${LOCAL_DIR}/" "${ILAB_USER}@${host}:${REMOTE_DIR}/" \
    >>"$LOGFILE" 2>&1
}

clear_remote_client_outputs_once() {
  # clear client outputs to avoid mixing old runs.
  echo "==> Clearing remote CLIENT results/plots so final pull only contains THIS sweep" | tee -a "$LOGFILE"
  ssh_block "$CLIENT_SSH_HOST" "
cd '${REMOTE_DIR}'
rm -rf results plots
mkdir -p results plots
"
}

get_server_ipv4() {
  ssh_cmd "$SERVER_SSH_HOST" "python3 - <<'PY'
import re, subprocess
out = subprocess.check_output(['hostname','-I'], text=True)
ips = [x for x in out.split() if re.fullmatch(r'(\\d+\\.){3}\\d+', x)]
print(ips[0] if ips else '')
PY" | tr -d '\r'
}

sleep_for_load() {
  local clients="$1"
  if [ "$clients" -ge 100 ]; then
    sleep "$HEAVY_DELAY"
  else
    sleep "$DELAY"
  fi
}

start_server_bg() {
  local proto="$1" payload="$2" requests="$3" clients="$4"

  echo "==> Starting ${proto} server on ${SERVER_SSH_HOST} (payload=${payload}, clients=${clients}, requests=${requests})" | tee -a "$LOGFILE"
  ensure_remote_dirs "$SERVER_SSH_HOST"

  ssh_block "$SERVER_SSH_HOST" "
cd '${REMOTE_DIR}'

# Stop previous server if pid exists
if [[ -f server.pid ]]; then
  kill \$(cat server.pid) >/dev/null 2>&1 || true
  rm -f server.pid
fi

# Best-effort: kill python listeners on this port
for pid in \$(ss -lntp 2>/dev/null | awk '/:${PORT}/ && /python3/ {gsub(/.*pid=|,.*/,\"\",\$NF); print \$NF}'); do
  kill \"\$pid\" >/dev/null 2>&1 || true
done
for pid in \$(ss -lunpt 2>/dev/null | awk '/:${PORT}/ && /python3/ {gsub(/.*pid=|,.*/,\"\",\$NF); print \$NF}'); do
  kill \"\$pid\" >/dev/null 2>&1 || true
done

rm -f server.out
: > server.out

nohup python3 server.py \
  --proto ${proto} \
  --bind ${BIND} \
  --port ${PORT} \
  --payload-bytes ${payload} \
  --requests ${requests} \
  --clients ${clients} \
  --log results/server \
  > server.out 2>&1 </dev/null &

echo \$! > server.pid

sleep 0.5
ss -lntp 2>/dev/null | grep :${PORT} || true
ss -lunp 2>/dev/null | grep :${PORT} || true
"
}

run_client_fg() {
  local proto="$1" payload="$2" requests="$3" clients="$4" server_ip="$5"
  echo "==> Running ${proto} client on ${CLIENT_SSH_HOST} (payload=${payload}, clients=${clients}, requests=${requests})" | tee -a "$LOGFILE"
  ensure_remote_dirs "$CLIENT_SSH_HOST"

  ssh_block "$CLIENT_SSH_HOST" "
cd '${REMOTE_DIR}'
python3 client.py \
  --proto ${proto} \
  --host \"${server_ip}\" \
  --port ${PORT} \
  --payload-bytes ${payload} \
  --requests ${requests} \
  --clients ${clients} \
  --log results
"
}

stop_server() {
  ssh_block "$SERVER_SSH_HOST" "
cd '${REMOTE_DIR}'
if [[ -f server.pid ]]; then
  kill \$(cat server.pid) >/dev/null 2>&1 || true
  rm -f server.pid
fi
" || true
}

cleanup() {
  echo | tee -a "$LOGFILE"
  echo "==> Cleanup: stopping server (best-effort)" | tee -a "$LOGFILE"
  stop_server
}
trap cleanup EXIT INT TERM

# Duplicate prevention 
is_seen() {
  local key="$1"
  [[ -f "$SEEN_FILE" ]] && grep -Fqx "$key" "$SEEN_FILE"
}
mark_seen() {
  local key="$1"
  echo "$key" >> "$SEEN_FILE"
}

run_one() {
  local proto="$1" payload="$2" clients="$3" requests="$4"
  local key="${proto}|${payload}|${clients}|${requests}"

  if is_seen "$key"; then
    echo "[$(date +%H:%M:%S)] SKIP duplicate proto=$proto payload=$payload clients=$clients requests=$requests" | tee -a "$LOGFILE"
    return 0
  fi
  mark_seen "$key"

  local attempt=0
  while true; do
    attempt=$((attempt + 1))
    echo "[$(date +%H:%M:%S)] RUN attempt=$attempt proto=$proto payload=$payload clients=$clients requests=$requests" | tee -a "$LOGFILE"

    if start_server_bg "$proto" "$payload" "$requests" "$clients" >>"$LOGFILE" 2>&1; then
      sleep 0.5
      if run_client_fg "$proto" "$payload" "$requests" "$clients" "$SERVER_IP" >>"$LOGFILE" 2>&1; then
        stop_server >>"$LOGFILE" 2>&1 || true
        echo "[$(date +%H:%M:%S)] OK  proto=$proto payload=$payload clients=$clients requests=$requests" | tee -a "$LOGFILE"
        break
      fi
    fi

    stop_server >>"$LOGFILE" 2>&1 || true

    if [ "$attempt" -gt "$RETRIES" ]; then
      echo "[$(date +%H:%M:%S)] FAIL (giving up) proto=$proto payload=$payload clients=$clients requests=$requests" | tee -a "$LOGFILE"
      return 1
    fi

    echo "[$(date +%H:%M:%S)] RETRYING in ${RETRY_SLEEP}s..." | tee -a "$LOGFILE"
    sleep "$RETRY_SLEEP"
  done

  sleep_for_load "$clients"
}

run_analysis_on_client() {
  local script_name="$1"

  if [ -z "$script_name" ]; then
    echo "ERROR: No analysis script filename provided." | tee -a "$LOGFILE"
    return 1
  fi

  echo "==> Running analysis on CLIENT: $script_name" | tee -a "$LOGFILE"

  ssh_block "$CLIENT_SSH_HOST" "
  cd '${REMOTE_DIR}'

  # Ensure output directories exist
  mkdir -p results plots

  # Run the specified analysis script
  python3 '$script_name'
  " | tee -a "$LOGFILE"
}

pull_client_end() {
  mkdir -p "${PULL_DIR}/client/results" "${PULL_DIR}/client/plots"
  echo "==> Pulling CLIENT results/ -> ${PULL_DIR}/client/results" | tee -a "$LOGFILE"
  sshpass -e rsync -az \
    -e "ssh ${SSH_OPTS[*]}" \
    "${ILAB_USER}@${CLIENT_SSH_HOST}:${REMOTE_DIR}/results/" \
    "${PULL_DIR}/client/results/" \
    >>"$LOGFILE" 2>&1

  echo "==> Pulling CLIENT plots/ -> ${PULL_DIR}/client/plots" | tee -a "$LOGFILE"
  sshpass -e rsync -az \
    -e "ssh ${SSH_OPTS[*]}" \
    "${ILAB_USER}@${CLIENT_SSH_HOST}:${REMOTE_DIR}/plots/" \
    "${PULL_DIR}/client/plots/" \
    >>"$LOGFILE" 2>&1

  echo "DONE ✅  Local sweep pull is in: ${PULL_DIR}/" | tee -a "$LOGFILE"
}

#############################################
# MAIN: experiment plan
#############################################
main() {
  need_cmd ssh
  need_cmd rsync
  need_cmd sshpass

  : > "$SEEN_FILE"

  prompt_pass_if_needed

  echo "Starting full sweep at $(date)" | tee -a "$LOGFILE"
  echo "Logging to $LOGFILE" | tee -a "$LOGFILE"

  ssh_test_login "$SERVER_SSH_HOST"
  ssh_test_login "$CLIENT_SSH_HOST"

  # Push files to each machine
  rsync_push_once "$SERVER_SSH_HOST"
  rsync_push_once "$CLIENT_SSH_HOST"

  SERVER_IP="$(get_server_ipv4)"
  [[ -n "$SERVER_IP" ]] || die "Could not determine server IPv4 on ${SERVER_SSH_HOST}"
  echo "==> Using server IPv4 for client traffic: ${SERVER_IP}" | tee -a "$LOGFILE"

  # Clear client outputs so end pull is clean
  clear_remote_client_outputs_once

  # ----------------
  # UDP vs TCP connection overhead 
  # ----------------
  PHASEA_PAYLOADS=(64 512 1024 4096 8192)
  PHASEA_CLIENTS=(1)
  PHASEA_REQUESTS=1

  for proto in tcp udp; do
    for payload in "${PHASEA_PAYLOADS[@]}"; do
      for clients in "${PHASEA_CLIENTS[@]}"; do
        run_one "$proto" "$payload" "$clients" "$PHASEA_REQUESTS"
      done
    done
  done

  # ----------------
  # rtt vs payload for TCP vs UDP
  # ----------------
  PHASEB_PAYLOADS=(64 512 1024 4096 8192)
  PHASEB_CLIENTS=(1)
  PHASEB_REQUESTS=(50)

  for proto in tcp udp; do
    for payload in "${PHASEB_PAYLOADS[@]}"; do
      for clients in "${PHASEB_CLIENTS[@]}"; do
        run_one "$proto" "$payload" "$clients" "${PHASEB_REQUESTS[@]}"
      done
    done
  done

  # ----------------
  # UDP loss rate vs clients 
  # ----------------

  PHASEC_PAYLOADS=(512)
  PHASEC_CLIENTS=(10 20 40 80 120)
  PHASEC_REQUESTS=(10)

  for proto in tcp udp; do
    for payload in "${PHASEC_PAYLOADS[@]}"; do
      for clients in "${PHASEC_CLIENTS[@]}"; do
        run_one "$proto" "$payload" "$clients" "$PHASEC_REQUESTS"

      done
    done
  done

  # ----------------
  # THROUGHPUT RUN
  # ----------------
  PHASED_PAYLOADS=(64 512 1024 4096 8192)
  PHASED_CLIENTS=(10)         
  PHASED_REQUESTS=100         

  for proto in tcp udp; do
    for payload in "${PHASED_PAYLOADS[@]}"; do
      for clients in "${PHASED_CLIENTS[@]}"; do
        run_one "$proto" "$payload" "$clients" "$PHASED_REQUESTS"
      done
    done
  done


  # ----------------
  # LATENCY RUN 
  # ----------------
  LAT_PAYLOADS=(64 512 1024 4096 8192)
  LAT_CLIENTS=(1 10)        
  LAT_REQUESTS=200        

  for proto in tcp udp; do
    for payload in "${LAT_PAYLOADS[@]}"; do
      for clients in "${LAT_CLIENTS[@]}"; do
        run_one "$proto" "$payload" "$clients" "$LAT_REQUESTS"
      done
    done
  done

  # Generate plots on the client machine
  run_analysis_on_client succ_rate.py
  run_analysis_on_client thrput.py
  run_analysis_on_client udp_lost_rate.py
  run_analysis_on_client latency.py
  run_analysis_on_client conn_overhead.py
  run_analysis_on_client rtt_vs_pload.py
  run_analysis_on_client conn_overhead_1.py

  # pull files to local machine for report
  pull_client_end

  echo "Sweep complete at $(date)" | tee -a "$LOGFILE"
}

main "$@"