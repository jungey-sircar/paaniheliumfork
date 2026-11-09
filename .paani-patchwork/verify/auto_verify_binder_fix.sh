#!/usr/bin/env bash
# Wait for the in-flight relink to finish, then immediately run the staged
# ad-blocker verification chain against a fresh headless Paani profile.
#
#   bash auto_verify_binder_fix.sh <build-wrapper-pid>
set -u
ROOT=/e/eric/PaaniBrowserChromiumFork
VERIFY=$ROOT/.paani-patchwork/verify
OUT=$ROOT/paani-windows/build/src/out/Default
LOGS=$VERIFY/logs
BUILD_LOG=$VERIFY/logs/paani_binder_fix.log
WRAP_PID=${1:-17376}
PORT=${2:-9338}
PROFILE=${3:-profile8}
BUILD_LOG=${4:-$ROOT/.paani-patchwork/logs/paani_binder_fix.log}
RESULT=$LOGS/auto_verify_result.txt

alive() {
  powershell -NoProfile -Command "if (Get-Process -Id $WRAP_PID -ErrorAction SilentlyContinue) { 'yes' } else { 'no' }" 2>/dev/null | tr -d '\r'
}

{
  echo "=== waiting for build wrapper pid $WRAP_PID (started $(date +%H:%M:%S)) ==="
  while [ "$(alive)" = "yes" ]; do sleep 20; done
  echo "build wrapper exited at $(date +%H:%M:%S)"

  echo
  echo "=== build verdict ==="
  tail -c 4000 "$BUILD_LOG" 2>/dev/null
  echo
  ls -la --time-style=+%H:%M:%S "$OUT/paani.dll" "$OUT/paani.exe" "$OUT/mini_installer.exe" "$OUT/setup.exe" 2>/dev/null

  echo
  echo "=== freeing the pak lock (paani.exe from this out dir only) ==="
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Process paani -ErrorAction SilentlyContinue | Where-Object { \$_.Path -like '$OUT*' } | ForEach-Object { Stop-Process -Id \$_.Id -Force; 'killed ' + \$_.Id }"

  echo
  echo "=== launching headless paani ($PROFILE, port $PORT) ==="
  powershell -NoProfile -ExecutionPolicy Bypass -File "$VERIFY/launch_diag.ps1" "$PROFILE" "$PORT"

  echo
  echo "=== waiting for CDP endpoint ==="
  for i in $(seq 1 40); do
    if curl -s -m 2 "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1; then
      echo "CDP up after ${i} tries ($(date +%H:%M:%S))"; break
    fi
    sleep 3
  done
  curl -s -m 3 "http://127.0.0.1:$PORT/json/version" || echo "CDP NEVER CAME UP"

  echo
  echo "=== engine startup lines from $PROFILE.err ==="
  sleep 5
  grep -a -E "Paani: |No binder found|paani_adblock|ad blocker" "$LOGS/$PROFILE.err" 2>/dev/null | head -40 || echo "(no Paani lines yet)"

  echo
  echo "=== verification chain ==="
  cd "$VERIFY" && node verify_paani.mjs "$PORT" 2>&1

  echo
  echo "=== engine lines after the run ==="
  grep -a -E "Paani: |No binder found" "$LOGS/$PROFILE.err" 2>/dev/null | head -40
  echo "=== done $(date +%H:%M:%S) ==="
} 2>&1 | tee "$RESULT"
