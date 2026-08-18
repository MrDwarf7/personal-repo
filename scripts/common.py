#!/usr/bin/env python3
# noqa: CPY001
"""Shared helpers and a tiny strategy/registry engine for repo tooling.

Every repo script follows the same shape: discover packages, run a strategy
per package, report. This module provides that skeleton so new tools are just
a registered strategy + a thin CLI -- no duplicated discovery/iteration code.

Patterns used (consistent across scripts/):
  - Package: dataclass describing one package directory.
  - Strategy: a callable with .name and .run(pkg) -> StrategyResult.
    Register with @strategy("name") and invoke via run_strategies().
  - run_strategies(pkgs, strategies, quiet) iterates and collects results,
    returning (results, failures) so callers decide exit codes.

To add a new tool:
  1. Write a module that defines one or more @strategy functions.
  2. In its __main__, call discover_packages() and run_strategies().
No changes to this file are needed.
"""

from __future__ import annotations
from typing import Callable

import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "_template"
EXCLUDED_DIRS = {"_template"}  # never a real package


@dataclass
class Package:
    """One package directory in the repo."""

    name: str
    path: Path

    @property
    def pkgbuild(self) -> Path:
        return self.path / "PKGBUILD"

    @property
    def check_sh(self) -> Path:
        return self.path / "check.sh"

    @property
    def update_sh(self) -> Path:
        return self.path / "update.sh"

    def has_pkgbuild(self) -> bool:
        return self.pkgbuild.is_file()

    def has_check(self) -> bool:
        return self.check_sh.is_file()

    def has_update(self) -> bool:
        return self.update_sh.is_file()

    def current_pkgver(self) -> str | None:
        if not self.has_pkgbuild():
            return None
        for line in self.pkgbuild.read_text().splitlines():
            if line.startswith("pkgver="):
                return line.split("=", 1)[1].strip().strip("'\"")
        return None

    def pkgname(self) -> str:
        """The pkgname declared in PKGBUILD (may differ from the dir name, e.g.
        cal-com/ has pkgname=cal-com-bin). Falls back to dir name."""
        if not self.has_pkgbuild():
            return self.name
        for line in self.pkgbuild.read_text().splitlines():
            if line.startswith("pkgname="):
                return line.split("=", 1)[1].strip().strip("'\"")
        return self.name

    def wired_names(self) -> set[str]:
        """Names by which this package may be registered: dir name + pkgname."""
        return {self.name, self.pkgname()}


def discover_packages(root: Path = REPO_ROOT) -> list[Package]:
    """Find every top-level dir containing a PKGBUILD (excluding _template)."""
    pkgs: list[Package] = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if d.name in EXCLUDED_DIRS:
            continue
        if (d / "PKGBUILD").is_file():
            pkgs.append(Package(name=d.name, path=d))
    return pkgs


@dataclass
class StrategyResult:
    package: str
    ok: bool
    detail: str = ""

    def __str__(self) -> str:
        mark = "ok " if self.ok else "FAIL"
        base = f"  [{mark}] {self.package}"
        return base + (f" -- {self.detail}" if self.detail else "")


# A strategy is just a callable (pkgname, Package) -> StrategyResult. The
# @strategy decorator attaches a .name attribute for display. We keep the
# StrategyResult return type as the contract.
StrategyFn = Callable[[Package], StrategyResult]

_REGISTRY: dict[str, StrategyFn] = {}


def strategy(name: str) -> Callable[[Callable], Callable]:
    """Decorator: register a function as a named strategy."""

    def deco(
        fn: Callable[[Package], StrategyResult],
    ) -> Callable[[Package], StrategyResult]:
        fn.name = name  # type: ignore[attr-defined]
        _REGISTRY[name] = fn  # type: ignore[assignment]
        return fn

    return deco


def get_strategy(name: str) -> StrategyFn | None:
    return _REGISTRY.get(name)


def list_strategies() -> list[str]:
    return sorted(_REGISTRY)


def run_strategies(
    pkgs: list[Package],
    strategies: list[StrategyFn],
    quiet: bool = False,
) -> tuple[list[StrategyResult], int]:
    """Run each strategy against each package; return (results, fail_count)."""
    results: list[StrategyResult] = []
    failures = 0
    for st in strategies:
        if not quiet:
            print(f"== {getattr(st, 'name', st.__name__)} ==")
        for pkg in pkgs:
            try:
                # Strategies are plain functions registered by @strategy.
                res = st(pkg)
            except Exception as e:  # noqa: BLE001 -- report, don't abort
                res = StrategyResult(pkg.name, False, f"exception: {e}")
            results.append(res)
            if not res.ok:
                failures += 1
            if not quiet or not res.ok:
                print(res)
    return results, failures


def run_check_script(pkg: Package) -> tuple[str | None, int]:
    """Run a package's check.sh, returning (version_or_None, returncode)."""
    if not pkg.has_check():
        return (None, 2)
    proc = subprocess.run(
        ["bash", str(pkg.check_sh)],
        cwd=pkg.path,
        capture_output=True,
        text=True,
    )
    out = proc.stdout.strip()
    return (out or None, proc.returncode)


def verify_matrix_packages(root: Path = REPO_ROOT) -> set[str]:
    """Package names listed in the verify.yml hardcoded matrix."""
    yml = root / ".github" / "workflows" / "verify.yml"
    names: set[str] = set()
    if not yml.is_file():
        return names
    in_matrix = False
    for line in yml.read_text().splitlines():
        s = line.strip()
        if s.startswith("matrix:"):
            in_matrix = True
            continue
        if in_matrix:
            if s.startswith("- ") and "package:" not in s:
                names.add(s[2:].strip())
            elif s and not s.startswith("-") and not s.startswith("#"):
                # left the matrix block
                if not s.startswith("package"):
                    in_matrix = False
    return names


def readme_package_rows(root: Path = REPO_ROOT) -> set[str]:
    """Package names present in the README package table."""
    md = root / "README.md"
    names: set[str] = set()
    if not md.is_file():
        return names
    in_table = False
    for line in md.read_text().splitlines():
        if line.strip().startswith("| Package"):
            in_table = True
            continue
        if in_table:
            if not line.strip().startswith("|"):
                break
            cell = line.split("|")[1].strip()
            if cell and cell != "Package":
                names.add(cell)
    return names
