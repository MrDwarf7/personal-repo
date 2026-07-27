#!/bin/bash
# Output the latest upstream version to stdout.
# Exit 0 + version = version found. Exit 1 = could not determine.
set -uo pipefail

# xeet publishes GitHub releases tagged vX.Y.Z (e.g. v0.1.9).
curl -sfL "https://api.github.com/repos/melqtx/xeet/releases/latest" \
  | grep '"tag_name":' \
  | sed -E 's/.*"v?([0-9][0-9.]*[0-9])".*/\1/'
