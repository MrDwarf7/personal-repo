#!/bin/bash
# Bumps pkgver when upstream has a newer version.
# Exits 0 whether or not a change was made (safe for CI loops).
set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PKGBUILD="$DIR/PKGBUILD"

current=$(grep -m1 '^pkgver=' "$PKGBUILD" | cut -d= -f2)
upstream=$(bash "$DIR/check.sh") || { echo "Could not determine upstream version"; exit 0; }

if [ "$upstream" = "$current" ]; then
  echo "Already up to date ($current)"
  exit 0
fi

echo "Bumping $current -> $upstream"
sed -i "s/^pkgver=.*/pkgver=${upstream}/" "$PKGBUILD"
sed -i "s/^pkgrel=.*/pkgrel=1/" "$PKGBUILD"

# Recompute checksums unless sources are SKIP or a NO_CHECKSUMS marker is present.
if [ ! -f "$DIR/NO_CHECKSUMS" ] \
   && grep -qE '^sha[0-9]*sums=' "$PKGBUILD" \
   && ! grep -q 'SKIP' "$PKGBUILD"; then
  ( cd "$DIR" && updpkgsums )
fi
