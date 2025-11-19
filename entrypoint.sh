#!/bin/bash
set -e

COMMAND="$1"

case "$COMMAND" in
  "legatus")
    echo "--- Starting Legatus Analyst Pipeline ---"
    # Shift arguments so $1 is removed, passing any remaining args to python
    shift
    exec python -m src.legatus_ai.legatus "$@"
    ;;

  "inquisitor")
    echo "--- Starting Inquisitor Q&A Agent ---"
    shift
    exec python -m src.legatus_ai.inquisitor "$@"
    ;;

  "setup")
    echo "--- Running Project Setup ---"
    shift
    exec python -m src.legatus_ai.setup "$@"
    ;;

  *)
    # If the command is not one of our aliases, just execute it as-is.
    exec "$@"
    ;;
esac
