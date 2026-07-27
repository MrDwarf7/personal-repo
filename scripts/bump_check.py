#!/usr/bin/env python3
"""Report which packages have a newer upstream version available.

Runs each package's check.sh, compares to the pkgver in its PKGBUILD, and
prints a table. This is the on-demand equivalent of update.yml's daily cron:
answer "what's stale?" in one call without pushing/committing anything.

Usage:
  python3 scripts/bump_check.py [--quiet] [--pkg NAME]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import common
from common import Package, StrategyResult, discover_packages, run_check_script, strategy

PADDING = 22


@strategy("upstream-version")
def check_bump(pkg: Package) -> StrategyResult:
    current = pkg.current_pkgver()
    if current is None:
        return StrategyResult(pkg.name, False, "no pkgver")
    upstream, rc = run_check_script(pkg)
    if rc != 0 or upstream is None:
        return StrategyResult(pkg.name, False, "upstream unknown (check.sh failed)")
    if upstream == current:
        return StrategyResult(pkg.name, True, f"up to date ({current})")
    return StrategyResult(pkg.name, False, f"bump {current} -> {upstream}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quiet", action="store_true", help="only print failures")
    ap.add_argument("--pkg", help="limit to one package")
    args = ap.parse_args()

    pkgs = discover_packages()
    if args.pkg:
        pkgs = [p for p in pkgs if p.name == args.pkg]
        if not pkgs:
            print(f"no such package: {args.pkg}", file=sys.stderr)
            return 2

    st = common.get_strategy("upstream-version")
    assert st is not None
    results, failures = common.run_strategies(pkgs, [st], quiet=args.quiet)

    if not args.quiet:
        stale = [r for r in results if not r.ok and "up to date" not in r.detail]
        print(f"\n{len(stale)} package(s) need a bump." if stale
              else "\nAll packages up to date.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
