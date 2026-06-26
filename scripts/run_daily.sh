#!/bin/bash
# Daily refresh: rerun the pipeline, then push the updated docs/ to GitHub
# so the public Pages site shows the latest schedule.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

LOG_DIR="$PROJECT_DIR/data/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d).log"

PYTHON="${PYTHON:-/Library/Frameworks/Python.framework/Versions/3.13/bin/python3}"

{
  echo "=== run started $(date -Iseconds) ==="

  # Retry the whole pipeline if it fails (the early-morning Kalshi 429 spike
  # can outlast the per-request backoff). Wait between attempts so the spike
  # has time to pass before we try again. The until-condition is exempt from
  # `set -e`, so a failed attempt loops instead of aborting the script.
  max_attempts=4
  retry_wait=180
  attempt=1
  until "$PYTHON" -m src.run; do
    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "Pipeline failed after ${max_attempts} attempts — giving up."
      exit 1
    fi
    echo "Pipeline attempt ${attempt}/${max_attempts} failed; retrying in ${retry_wait}s..."
    sleep "$retry_wait"
    attempt=$((attempt + 1))
  done

  if git diff --quiet -- docs/; then
    echo "docs/ unchanged — nothing to publish."
  else
    git add docs/
    git -c user.name="$(git config user.name)" \
        -c user.email="$(git config user.email)" \
        commit -m "Daily refresh: $(date +%Y-%m-%d)"
    git push origin main
    echo "Published."
  fi

  echo "=== run finished $(date -Iseconds) ==="
} >> "$LOG_FILE" 2>&1
