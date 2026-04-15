#!/bin/bash
# Unsloth Studio launcher
# First run: sets up venv + installs packages via upstream installer
# Subsequent runs: launches the web UI
set -euo pipefail

STUDIO_HOME="$HOME/.unsloth/studio"
VENV_DIR="$STUDIO_HOME/unsloth_studio"
INSTALL_LOG="$STUDIO_HOME/install.log"

# ── First-run setup ──
if [ ! -x "$VENV_DIR/bin/unsloth" ]; then
  echo "==> First run: setting up Unsloth Studio..."
  echo "    This will create a Python venv and install PyTorch + unsloth."
  echo "    This may take several minutes on first run."
  echo ""

  mkdir -p "$STUDIO_HOME"

  # Run the upstream installer
  bash /opt/unsloth/install.sh 2>&1 | tee "$INSTALL_LOG"
  _rc=${PIPESTATUS[0]}

  if [ $_rc -ne 0 ]; then
    echo ""
    echo "==> Setup failed (exit code $_rc). Check $INSTALL_LOG for details."
    echo "    Re-run 'unsloth-studio' to retry."
    exit $_rc
  fi

  echo ""
  echo "==> Setup complete! Starting Unsloth Studio..."
  echo ""
fi

# ── Launch ──
# Find a free port starting from 8888
BASE_PORT=8888
_port=$BASE_PORT
while ss -tlnH 2>/dev/null | awk '{print $4}' | grep -qE "[.:]$_port$"; do
  _port=$((_port + 1))
  [ $_port -gt $((BASE_PORT + 20)) ] && { echo "No free port found"; exit 1; }
done

echo "==> Unsloth Studio starting on http://localhost:$_port"
exec "$VENV_DIR/bin/unsloth" studio -H 0.0.0.0 -p "$_port" "$@"
