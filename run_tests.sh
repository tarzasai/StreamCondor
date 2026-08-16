#!/usr/bin/env bash
set -euo pipefail

# Run pytest in the project using the project's virtualenv (if present)
SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPTDIR" && pwd)"

# Prefer project's venv python
PY="$ROOT_DIR/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3 || command -v python)"
fi

echo "Using Python: $PY"

# Default headless Qt and pytest-qt API to match VS Code test runs
export QT_QPA_PLATFORM=${QT_QPA_PLATFORM:-offscreen}
export PYTEST_QT_API=${PYTEST_QT_API:-pyqt6}

# Ensure package sources are importable
export PYTHONPATH=${PYTHONPATH:-$ROOT_DIR/src}

# Run pytest with any args passed through.
# --forked isolates each test in its own process, avoiding cross-file Qt/PyQt6
# state leakage that segfaults the shared-process run. Coverage should be
# collected via a separate run if needed.
exec "$PY" -m pytest --forked "$@"
