#!/bin/bash
# Output the latest upstream release tag to stdout (stripped of the leading v),
# e.g. "0.1.501.beta". Exit 0 + version = found. Exit 1 = could not determine.
# Arch pkgver policy forbids hyphens, so the upstream "X.Y.Z-beta" tag is
# rewritten to the dot form here; the PKGBUILD maps it back to vX.Y.Z-beta
# in the source URL.
set -uo pipefail

curl -sfL "https://api.github.com/repos/unslothai/unsloth/releases/latest" \
  | grep '"tag_name":' \
  | sed -E 's/.*"v?([0-9][0-9.]*)-beta".*/\1.beta/'
