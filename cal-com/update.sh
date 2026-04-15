#!/bin/bash
# Bumps pkgver if upstream has a newer version.
# Must be run from the package directory.
# Exits 0 — changed PKGBUILD if update needed, no-op if up to date.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PKGBUILD="$DIR/PKGBUILD"

current=$(grep -m1 '^pkgver=' "$PKGBUILD" | cut -d= -f2)

# Get upstream version — source is the package's check.sh
upstream=$("$DIR/check.sh") || { echo "Could not determine upstream version"; exit 0; }

if [ "$upstream" = "$current" ]; then
  echo "Already up to date ($current)"
  exit 0
fi

echo "Bumping $current -> $upstream"
sed -i "s/^pkgver=.*/pkgver=${upstream}/" "$PKGBUILD"
sed -i "s/^pkgrel=.*/pkgrel=1/" "$PKGBUILD"

# Recompute checksums for the new source
cd "$DIR"
updpkgsums
