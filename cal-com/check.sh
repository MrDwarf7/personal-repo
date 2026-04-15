#!/bin/bash
# Outputs the latest upstream version to stdout.
# Exit 0 with version = version available
# Exit 1 = could not determine version
curl -sf "https://download.todesktop.com/220806rvletlw4t/latest-linux.yml" \
  | grep '^version:' | awk '{print $2}'
