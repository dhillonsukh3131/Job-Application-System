#!/usr/bin/env bash
set -euo pipefail

# Run from repo root by default; override with APP_DIR env var.
APP_DIR="${APP_DIR:-/workspace/Job-Application-System}"
PYTHON_BIN="${PYTHON_BIN:-python}"

NAME="${NAME:-Your Name}"
SKILLS="${SKILLS:-Python,Machine Learning,LLMs,PyTorch}"
REGIONS="${REGIONS:-United States,Europe,Asia,Remote}"
MAX_RESULTS="${MAX_RESULTS:-50}"
TRACKER_CSV="${TRACKER_CSV:-data/ai_internships_tracker.csv}"
EXTRA_KEYWORDS="${EXTRA_KEYWORDS:-}"
EXCLUDE_KEYWORDS="${EXCLUDE_KEYWORDS:-}"
SHEETS_WEBHOOK_URL="${GOOGLE_SHEETS_WEBHOOK_URL:-${SHEETS_WEBHOOK_URL:-}}"

cd "$APP_DIR"

CMD=(
  "$PYTHON_BIN" ai_internship_multi_agent.py
  --name "$NAME"
  --skills "$SKILLS"
  --regions "$REGIONS"
  --max-results "$MAX_RESULTS"
  --tracker-csv "$TRACKER_CSV"
)

if [[ -n "$EXTRA_KEYWORDS" ]]; then
  CMD+=(--extra-keywords "$EXTRA_KEYWORDS")
fi

if [[ -n "$EXCLUDE_KEYWORDS" ]]; then
  CMD+=(--exclude-keywords "$EXCLUDE_KEYWORDS")
fi

if [[ -n "$SHEETS_WEBHOOK_URL" ]]; then
  CMD+=(--sheets-webhook-url "$SHEETS_WEBHOOK_URL")
fi

"${CMD[@]}"
