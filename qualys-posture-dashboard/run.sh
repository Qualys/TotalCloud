#!/usr/bin/env bash
# Convenience wrapper — the real launcher is the cross-platform run.py.
#   ./run.sh                 → foreground (Ctrl+C to stop)
#   ./run.sh start|stop|status
#   ./run.sh --demo | --port 9000
cd "$(dirname "$0")"
exec python3 run.py "$@"
