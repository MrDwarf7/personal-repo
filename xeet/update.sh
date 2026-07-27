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

# Recompute the source checksum for the new upstream tarball.
( cd "$DIR" && updpkgsums )
