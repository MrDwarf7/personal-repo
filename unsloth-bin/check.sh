#!/bin/bash
# Outputs the latest unsloth version from PyPI
curl -sf "https://pypi.org/pypi/unsloth/json" | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])"
