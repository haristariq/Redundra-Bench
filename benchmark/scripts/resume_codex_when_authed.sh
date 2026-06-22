#!/bin/bash
# Wait until the Codex (ChatGPT-subscription) login is valid again, then resume
# the remaining Phase-0 cells and analyze. Polls every 5 min, up to 12 hours.
#
# Blocked by an auth-token rotation issue that requires the user to run
# `codex login`; once they do, the next probe succeeds and the resume fires.
#
# Usage:  bash benchmark/scripts/resume_codex_when_authed.sh
set -u
cd "$(dirname "$0")/../.." || exit 1
LOG=benchmark/results/phase0.resume.log
RUN_ID=phase0
echo "$(date) watcher started; waiting for codex auth" >> "$LOG"

for i in $(seq 1 288); do
  T=$(mktemp -d)
  if env -u CODEX_HOME timeout 90 codex exec --skip-git-repo-check --sandbox read-only \
       -C "$T" -c 'model_reasoning_effort="low"' "Reply with exactly: AUTHOK" >/dev/null 2>&1; then
    echo "$(date) codex OK (attempt $i) — resuming remaining cells" >> "$LOG"
    python3 benchmark/runner/run_all.py --run-id "$RUN_ID" --seeds 5 --timeout 360 >> "$LOG" 2>&1
    echo "$(date) resume run finished; analyzing" >> "$LOG"
    python3 benchmark/analysis/analyze.py "$RUN_ID" >> "$LOG" 2>&1
    echo "$(date) DONE" >> "$LOG"
    exit 0
  fi
  echo "$(date) codex unavailable (attempt $i/288) — usage limit or auth; will retry" >> "$LOG"
  sleep 300
done
echo "$(date) gave up after 24h without working codex" >> "$LOG"
exit 2
