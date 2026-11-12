#!/usr/bin/env bash
# run.sh - Launch Ubuntu Performance Track Topbar Application

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
export PYTHONPATH="$DIR:$PYTHONPATH"

# Run the app
exec python3 -m performance_track.app "$@"
