#!/usr/bin/env bash
# Start the cheddar API detached from the current terminal.
# Reads required variables from .env (gitignored) in the repo root.
# Logs go to .api.log, the PID to .api.pid.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

HOST="${CHEDDAR_API_HOST:-127.0.0.1}"
PORT="${CHEDDAR_API_PORT:-8000}"
PID_FILE=".api.pid"
LOG_FILE=".api.log"

if [[ ! -f .env ]]; then
  echo "error: .env not found. Create it with:" >&2
  echo "  CHEDDAR_IMAP_USER=you@example.com" >&2
  echo "  CHEDDAR_IMAP_PASSWORD=app-password" >&2
  exit 1
fi

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "error: API already running (pid $(cat "$PID_FILE")). Stop it with: kill $(cat "$PID_FILE")" >&2
  exit 1
fi

# Export everything defined in .env.
set -a
# shellcheck disable=SC1091
source .env
set +a

for var in CHEDDAR_IMAP_USER CHEDDAR_IMAP_PASSWORD; do
  if [[ -z "${!var:-}" ]]; then
    echo "error: $var is not set in .env" >&2
    exit 1
  fi
done

nohup uv run uvicorn main:app --app-dir api --host "$HOST" --port "$PORT" \
  >"$LOG_FILE" 2>&1 < /dev/null &
echo $! > "$PID_FILE"
disown

echo "API started (pid $(cat "$PID_FILE")) on http://$HOST:$PORT"
echo "Logs: $LOG_FILE | Stop: kill \$(cat $PID_FILE)"
