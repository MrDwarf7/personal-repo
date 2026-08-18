#!/usr/bin/env python3
# noqa: CPY001
"""Validate every package's PKGBUILD builds cleanly (source fetch + checks).

Runs `makepkg --nobuild` per package in its directory so CI-equivalent issues
surface locally before push. If `namcap` is installed it is run too. The
full build (npm/python wheel/compile) is NOT run here -- that happens in the
cachyos container; `--nobuild` catches source/checksum/dep/syntax errors.

Usage:
  python3 scripts/validate_all.py [--quiet] [--pkg NAME]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

import common
from common import Package, StrategyResult, discover_packages, strategy


@strategy("makepkg-nobuild")
def validate_pkgbuild(pkg: Package) -> StrategyResult:
    if not pkg.has_pkgbuild():
        return StrategyResult(package=pkg.name, ok=False, detail="no PKGBUILD")
    mkpkg_exe = shutil.which("makepkg")
    if not mkpkg_exe:
        return StrategyResult(
            package=pkg.name, ok=False, detail="makepkg not installed"
        )
    proc = subprocess.run(  # noqa: S603
        [mkpkg_exe, "--nobuild", "--noconfirm"],
        cwd=pkg.path,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        # surface the tail so the failure is diagnosable
        tail = "\n".join(proc.stdout.strip().splitlines()[-4:])
        return StrategyResult(
            package=pkg.name, ok=False, detail=f"rc={proc.returncode}\n{tail}"
        )
    return StrategyResult(
        package=pkg.name, ok=True, detail="makepkg --nobuild ok"
    )


@strategy("namcap")
def lint_namcap(pkg: Package) -> StrategyResult:
    if shutil.which("namcap") is None:
        return StrategyResult(
            package=pkg.name, ok=True, detail="namcap not installed (skipped)"
        )
    if not pkg.has_pkgbuild():
        return StrategyResult(package=pkg.name, ok=False, detail="no PKGBUILD")

    namcap_exe = shutil.which("namcap")
    if not namcap_exe:
        return StrategyResult(
            package=pkg.name, ok=False, detail="namcap not installed"
        )

    proc = subprocess.run(  # noqa: S603
        [namcap_exe, str(pkg.pkgbuild)],
        cwd=pkg.path,
        capture_output=True,
        text=True,
        check=False,
    )
    # namcap returns 0 even with warnings; treat output lines as the signal.
    out = proc.stdout.strip()
    # Heuristic: a clean run prints only "<file>: ... PKGBUILD" info lines.
    # Warnings/E errors contain ' W ' or ' E '.
    problems = [
        line for line in out.splitlines() if " E " in line or " W " in line
    ]
    if problems:
        return StrategyResult(
            package=pkg.name,
            ok=False,
            detail="namcap:\n" + "\n".join(problems[:5]),
        )
    msg = "namcap clean" if out else "namcap clean (no output)"

    return StrategyResult(package=pkg.name, ok=True, detail=msg)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--pkg", help="limit to one package")
    ap.add_argument("--skip-namcap", action="store_true")
    args = ap.parse_args()

    pkgs = discover_packages()
    if args.pkg:
        pkgs = [p for p in pkgs if p.name == args.pkg]
        if not pkgs:
            print(f"no such package: {args.pkg}", file=sys.stderr)
            return 2

    strategies = [common.get_strategy("makepkg-nobuild")]
    strategies = [s for s in strategies if s is not None]

    appendable_strategies = [common.get_strategy("namcap")]
    appendable_strategies = [s for s in appendable_strategies if s is not None]

    if not args.skip_namcap:
        strategies.extend(appendable_strategies)

    assert all(s is not None for s in strategies)  # noqa: S101

    _, failures = common.run_strategies(pkgs, strategies, quiet=args.quiet)  # type: ignore[arg-type]
    if not args.quiet:
        print(f"\n{'PASS' if failures == 0 else 'FAIL'}: {failures} issue(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
