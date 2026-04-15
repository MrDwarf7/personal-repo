#!/bin/bash
# Output the latest upstream version to stdout.
# Exit 0 + version = version found. Exit 1 = could not determine.
set -uo pipefail

# Pick the method matching your upstream and delete the rest.

# Method A: GitHub latest release tag
# curl -sfL "https://api.github.com/repos/OWNER/REPO/releases/latest" \
#   | grep '"tag_name":' | sed -E 's/.*"v?([0-9.]+)".*/\1/'

# Method B: Electron/ToDesktop latest-linux.yml
# curl -sfL "https://download.todesktop.com/APPID/latest-linux.yml" \
#   | grep '^version:' | awk '{print $2}'

# Method C: PyPI JSON API
# curl -sfL "https://pypi.org/pypi/PKG/json" \
#   | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])"

# Method D: static URL with version in path
# curl -sfIL "https://example.com/thing-latest.tar.gz" \
#   | grep -oP 'thing-\K[0-9.]+(?=\.tar\.gz)' | head -1
