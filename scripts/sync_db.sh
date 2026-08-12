#!/bin/bash
# Refresh the local pacman database (the "paru -Syy" step).
#
# Honors $PKG_MANAGER if set (e.g. paru), otherwise detects
# an available helper in the order paru -> yay -> pacman. pacman needs root
# for -Syy, so it is wrapped in sudo; the AUR helpers handle privileges
# themselves.
set -uo pipefail

mgr="${PKG_MANAGER:-}"
if [ -z "$mgr" ]; then
  for c in paru yay pacman; do
    if command -v "$c" >/dev/null 2>&1; then
      mgr="$c"
      break
    fi
  done
fi

if [ -z "$mgr" ]; then
  echo "No AUR helper or pacman found (looked for paru, yay, pacman)." >&2
  exit 1
fi

if ! command -v "$mgr" >/dev/null 2>&1; then
  echo "PKG_MANAGER is set to '$mgr' but that binary is not on PATH." >&2
  exit 1
fi

echo "Refreshing pacman databases via '$mgr'..."
if [ "$mgr" = "pacman" ]; then
  sudo pacman -Syy
else
  "$mgr" -Syy
fi
