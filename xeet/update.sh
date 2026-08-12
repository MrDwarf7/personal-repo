#!/bin/bash
# Bumps pkgver when upstream has a newer version.
# Exits 0 whether or not a change was made (safe for CI loops).
set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PKGBUILD="$DIR/PKGBUILD"

# updpkgsums (pacman-contrib) is REQUIRED to recompute checksums after a
# bump. Fail loud BEFORE touching pkgver so a bump can never be committed
# with a stale checksum (which makes every subsequent build fail in
# makepkg's source validation). The update cron runs inside an Arch
# container that has pacman-contrib installed, so this only trips when the
# tooling is genuinely missing.
if ! command -v updpkgsums >/dev/null 2>&1; then
  echo "error: updpkgsums not found (install pacman-contrib)" >&2
  exit 1
fi

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
