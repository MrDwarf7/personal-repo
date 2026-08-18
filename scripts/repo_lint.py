#!/usr/bin/env python3
# noqa: CPY001
"""Consistency guard: detect repo wiring drift.

Checks every package is fully wired in (verify.yml matrix + README table) and
has the expected files. Fails loudly on drift so a forgotten edit is caught
before push. Scales by adding more @strategy checks here.

Usage:
  python3 scripts/repo_lint.py [--quiet] [--pkg NAME]
"""

from __future__ import annotations

import argparse
import sys

import common
from common import (
    Package,
    StrategyResult,
    discover_packages,
    readme_package_rows,
    strategy,
    verify_matrix_packages,
)


@strategy("verify-matrix-wired")
def check_verify_matrix(pkg: Package) -> StrategyResult:
    wired = pkg.wired_names() & verify_matrix_packages()
    return StrategyResult(
        pkg.name, bool(wired), "" if wired else "missing from verify.yml matrix"
    )


@strategy("readme-table-wired")
def check_readme_table(pkg: Package) -> StrategyResult:
    wired = pkg.wired_names() & readme_package_rows()
    return StrategyResult(
        pkg.name, bool(wired), "" if wired else "missing from README table"
    )


@strategy("has-check-script")
def check_has_check(pkg: Package) -> StrategyResult:
    ok = pkg.has_check()
    return StrategyResult(pkg.name, ok, "" if ok else "no check.sh")


@strategy("has-update-script")
def check_has_update(pkg: Package) -> StrategyResult:
    ok = pkg.has_update()
    return StrategyResult(pkg.name, ok, "" if ok else "no update.sh")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--pkg", help="limit to one package")
    args = ap.parse_args()

    pkgs = discover_packages()
    if args.pkg:
        pkgs = [p for p in pkgs if p.name == args.pkg]
        if not pkgs:
            print(f"no such package: {args.pkg}", file=sys.stderr)
            return 2

    strategies = [
        common.get_strategy("verify-matrix-wired"),
        common.get_strategy("readme-table-wired"),
        common.get_strategy("has-check-script"),
        common.get_strategy("has-update-script"),
    ]
    strategies = [s for s in strategies if s is not None]

    assert all(s is not None for s in strategies)  # noqa: S101
    _, failures = common.run_strategies(pkgs, strategies, quiet=args.quiet)  # type: ignore[arg-type]
    if not args.quiet:
        print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {failures} issue(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
