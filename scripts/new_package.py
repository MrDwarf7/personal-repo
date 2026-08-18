#!/usr/bin/env python3
# noqa: CPY001

"""Scaffold a new package in the personal-repo and wire it in.

Copies `_template/` to `<pkgname>/`, then wires the new package into the
two repo-specific bits that are NOT auto-discovered by CI:

  - .github/workflows/verify.yml  : hardcoded PR-verify matrix
  - README.md                      : package table row

`build.yml` and `update.yml` discover packages automatically (they glob
`*/PKGBUILD` and `*/update.sh`), so they need no edits.

By default this runs DRY: it prints the edits it would make and changes
nothing. Pass --apply to actually write. This keeps it safe to re-run.

Usage:
  python3 scripts/new_package.py <pkgname> \
      --upstream "melqtx/xeet" \
      --type "Go source build (cgo + libX11)" \
      [--no-verify]            # skip adding to verify.yml matrix
      [--template-dir _template]

After running, fill in <pkgname>/PKGBUILD, check.sh, and update.sh.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import sys
from pathlib import Path
from typing import NoReturn, Optional, TYPE_CHECKING
import contextlib
import subprocess


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "_template"
VERIFY_YML = REPO_ROOT / ".github" / "workflows" / "verify.yml"
README = REPO_ROOT / "README.md"

# Process tracking for clean teardown. Agents often launch this script in the
# background and watch its PID, sending SIGTERM/SIGINT to cancel. Any children
# we spawn should be appended to _CHILDREN so the handler can kill them and we
# don't leave orphans behind. _CREATED_DIR is the package dir we are scaffolding
# (set before the copy so a mid-copy signal can roll it back).
_CHILDREN: list[subprocess.Popen[bytes]] = []
_CREATED_DIR: Path | None = None


def _handle_signal(signum: int, _frame: object) -> NoReturn:
    name = {signal.SIGINT.value: "SIGINT", signal.SIGTERM.value: "SIGTERM"}.get(
        signum, str(signum)
    )
    print(
        f"\n[pid {os.getpid()}] received {name}; cleaning up...",
        file=sys.stderr,
    )
    # Kill any child processes we spawned.
    for child in _CHILDREN:
        with contextlib.suppress(Exception):
            child.terminate()
    for child in _CHILDREN:
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(Exception):
                child.kill()
    # Remove a partially-created package dir so we don't leave the repo in a
    # half-wired state.
    if _CREATED_DIR is not None and _CREATED_DIR.exists():
        shutil.rmtree(_CREATED_DIR, ignore_errors=True)
        print(f"  removed partial package dir {_CREATED_DIR}", file=sys.stderr)
    sys.exit(130)


def die(msg: str) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def copy_template(pkgname: str, template_dir: str) -> Path:
    src = REPO_ROOT / template_dir
    if not src.is_dir():
        die(f"template dir not found: {src}")
    dst = REPO_ROOT / pkgname
    if dst.exists():
        die(f"target already exists: {dst} (refusing to overwrite)")
    shutil.copytree(src, dst)
    return dst


# Language-aware PKGBUILD starters. Each is a str.format template with the
# single field {pkgname}. Add a new language here to extend --lang without
# touching main().
PKGBUILD_TEMPLATES: dict[str, str] = {
    "go": """\
# Maintainer: Blake B. <mrdwarf7twitch at gmail dot com>

pkgname={pkgname}
pkgver=0.0.1
pkgrel=1
pkgdesc=''
arch=('x86_64' 'aarch64')
url=''
license=('MIT')
makedepends=('go' 'base-devel')
depends=(glibc)

source=("$pkgname-$pkgver.tar.gz::https://github.com/OWNER/REPO/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

prepare() {{
  cd "$pkgname-$pkgver"
  export GOPATH="$srcdir"
  go mod download -modcacherw
}}

build() {{
  cd "$pkgname-$pkgver"
  export CGO_CPPFLAGS="${{CPPFLAGS}}"
  export CGO_CFLAGS="${{CFLAGS}}"
  export CGO_CXXFLAGS="${{CXXFLAGS}}"
  export CGO_LDFLAGS="${{LDFLAGS}}"
  export GOFLAGS="-buildmode=pie -trimpath -ldflags=-linkmode=external -mod=readonly -modcacherw"
  export GOPATH="$srcdir"
  go build -o "$pkgname" .
}}

check() {{
  cd "$pkgname-$pkgver"
  export GOPATH="$srcdir"
  go test ./...
}}

package() {{
  cd "$pkgname-$pkgver"
  install -Dm755 "$pkgname" "$pkgdir/usr/bin/$pkgname"
}}
""",  # noqa: E501
    "rust": """\
# Maintainer: Blake B. <mrdwarf7twitch at gmail dot com>

pkgname={pkgname}
pkgver=0.0.1
pkgrel=1
pkgdesc=''
url=''
license=()
makedepends=('cargo')
depends=(gcc-libs glibc)
arch=('x86_64' 'aarch64')
source=("$pkgname-$pkgver.tar.gz::https://github.com/OWNER/REPO/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

prepare() {{
  export RUSTUP_TOOLCHAIN=stable
  cargo fetch --locked --target "$CARCH"
}}

build() {{
  export RUSTUP_TOOLCHAIN=stable
  export CARGO_TARGET_DIR=target
  cargo build --frozen --release --all-features
}}

check() {{
  export RUSTUP_TOOLCHAIN=stable
  cargo test --frozen --all-features
}}

package() {{
  install -Dm0755 -t "$pkgdir/usr/bin/" "target/release/$pkgname"
}}
""",
    "bin": """\
# Maintainer: Blake B. <mrdwarf7twitch at gmail dot com>

pkgname={pkgname}
pkgver=0.0.1
pkgrel=1
pkgdesc=''
arch=('x86_64')
url=''
license=('custom')
options=('!strip')
source=("$pkgname-$pkgver.tar.gz::https://example.com/$pkgname-$pkgver.tar.gz")
sha256sums=('SKIP')

package() {{
  install -Dm755 "$pkgname" "$pkgdir/usr/bin/$pkgname"
}}
""",
}


def scaffold_pkgbuild(pkgname: str, lang: str | None) -> str:
    """Return the PKGBUILD text to write, based on --lang or _template."""
    if lang and lang in PKGBUILD_TEMPLATES:
        return PKGBUILD_TEMPLATES[lang].format(pkgname=pkgname)
    # Fallback: read the bare proto from _template/PKGBUILD if present.
    proto = TEMPLATE_DIR / "PKGBUILD"
    if proto.is_file():
        return proto.read_text().replace("NAME", pkgname)
    # Last resort: minimal stub.
    return f"# Maintainer: Blake B. <mrdwarf7twitch at gmail dot com>\npkgname={pkgname}\npkgver=0.0.1\npkgrel=1\npkgdesc=''\narch=('x86_64')\nsource=()\nsha256sums=()\n"  # noqa: E501


def wire_verify(pkgname: str, text: str) -> str:
    """Insert `- <pkgname>` into the hardcoded verify.yml package matrix."""
    # Match the `package:` list under the verify job's strategy.matrix.
    pat = re.compile(r"(        package:\n(?:          - [^\n]*\n)+)")
    m = pat.search(text)
    if not m:
        die("could not locate the `package:` matrix in verify.yml")
    block = m.group(1)
    if f"- {pkgname}\n" in block:
        print(f"  (verify.yml: {pkgname} already present -- skipping)")
        return text
    new_block = block + f"          - {pkgname}\n"
    return text[: m.start(1)] + new_block + text[m.end(1) :]


def wire_readme(pkgname: str, upstream: str, ptype: str, text: str) -> str:
    """Append a row to the README package table."""
    lines = text.splitlines(keepends=True)
    # Find the header row `| Package ...` and the last contiguous table row.
    header_idx = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("|") and "Package" in ln and "Upstream" in ln:
            header_idx = i
            break
    if header_idx is None:
        die("could not locate the package table header in README.md")
    last_row = None
    for j in range(header_idx, len(lines)):
        if lines[j].lstrip().startswith("|"):
            last_row = j
        else:
            # Stop at the first non-table line after the header.
            break
    if last_row is None:
        die("package table has no data rows to append after")
    existing = "".join(lines[header_idx : last_row + 1])
    if f"| {pkgname} " in existing:
        print(f"  (README.md: {pkgname} already present -- skipping)")
        return text
    row = f"| {pkgname} | {upstream} | {ptype} |\n"
    out = [*lines[: last_row + 1], row, *lines[last_row + 1 :]]
    return "".join(out)


def argument_parser() -> tuple[argparse.Namespace, argparse.ArgumentParser]:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("pkgname", help="new package directory / pkgname")
    ap.add_argument(
        "--upstream",
        default="",
        help="upstream name for the README table (e.g. melqtx/xeet)",
    )
    ap.add_argument(
        "--type",
        dest="ptype",
        default="",
        help="package type for the README table (e.g. 'Go source build')",
    )
    ap.add_argument(
        "--no-verify",
        action="store_true",
        help="do not add the package to the verify.yml matrix",
    )
    ap.add_argument(
        "--lang",
        choices=["go", "rust", "bin"],
        default=None,
        help="language/build preset for the PKGBUILD starter "
        "(go=source build, rust=cargo, bin=prebuilt). "
        "Overrides --template-dir.",
    )
    ap.add_argument(
        "--template-dir",
        default="_template",
        help="scaffold source dir (default: _template)",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="actually write changes (default is dry-run)",
    )
    args = ap.parse_args()
    return (args, ap)


def main() -> None:  # noqa: PLR0912
    args, _ap = argument_parser()

    if not re.fullmatch(r"[A-Za-z0-9._+-]+", args.pkgname):
        die("pkgname must be a safe directory name (alphanumerics/._+-)")

    # Catch SIGINT/SIGTERM so an agent that launched us in the background and
    # later kills our PID gets a clean teardown: no orphaned children, no
    # half-created package directory left in the repo.
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # 1. Scaffold. Only --apply writes anything; dry-run reports only.
    dst = REPO_ROOT / args.pkgname
    if args.apply:
        global _CREATED_DIR  # noqa: PLW0603
        _CREATED_DIR = (
            dst  # set before any write so a mid-write SIGINT cleans up
        )
        if dst.exists():
            die(f"target already exists: {dst} (refusing to overwrite)")
        dst.mkdir()
        (dst / "PKGBUILD").write_text(
            scaffold_pkgbuild(args.pkgname, args.lang)
        )
        # Stub check.sh/update.sh so the package is fully wired from the start.
        (dst / "check.sh").write_text(
            "#!/bin/bash\n# Print latest upstream version to stdout.\n# Exit 0 + version = found; exit 1 = could not determine.\n"  # noqa: E501
            "set -uo pipefail\n\n# TODO: implement per-upstream version lookup\necho '0.0.1'\n"  # noqa: E501
        )
        (dst / "update.sh").write_text(
            '#!/bin/bash\n# Bump pkgver when upstream has a newer version.\nset -uo pipefail\n\nDIR="$(cd "$(dirname "$0")" && pwd)"\n'  # noqa: E501
            'PKGBUILD="$DIR/PKGBUILD"\ncurrent=$(grep -m1 \'^pkgver=\' "$PKGBUILD" | cut -d= -f2)\n'  # noqa: E501
            'upstream=$(bash "$DIR/check.sh") || { echo "Could not determine upstream version"; exit 0; }\n'  # noqa: E501
            'if [ "$upstream" = "$current" ]; then echo "Already up to date ($current)"; exit 0; fi\n'  # noqa: E501
            'echo "Bumping $current -> $upstream"\n'
            'sed -i "s/^pkgver=.*/pkgver=${upstream}/" "$PKGBUILD"\n'
            'sed -i "s/^pkgrel=.*/pkgrel=1/" "$PKGBUILD"\n'
            "# Recompute checksums unless sources are SKIP.\n"
            'if grep -qE \'^sha[0-9]*sums=\' "$PKGBUILD" && ! grep -q \'SKIP\' "$PKGBUILD"; then ( cd "$DIR" && updpkgsums ); fi\n'  # noqa: E501
        )
        # import os as _os

        Path.chmod(dst / "check.sh", 0o755)
        Path.chmod(dst / "update.sh", 0o755)
        src = "lang=" + (args.lang or "proto")
        print(f"  + created {dst.relative_to(REPO_ROOT)}/ ({src})")
    else:
        print(
            f"  + would create {dst.relative_to(REPO_ROOT)}/ (lang={args.lang or 'proto'})"  # noqa: E501
        )

    # 2. Wire verify.yml matrix
    if not args.no_verify:
        vtext = VERIFY_YML.read_text() if VERIFY_YML.exists() else ""
        vnew = wire_verify(args.pkgname, vtext)
        if vnew != vtext:
            print(f"  ~ .github/workflows/verify.yml  (+ - {args.pkgname})")
            if args.apply:
                VERIFY_YML.write_text(vnew)
        else:
            print("  . .github/workflows/verify.yml  (no change)")

    # 3. Wire README table
    rtext = README.read_text() if README.exists() else ""
    rnew = wire_readme(args.pkgname, args.upstream, args.ptype, rtext)
    if rnew != rtext:
        print(
            f"  ~ README.md  (+ | {args.pkgname} | {args.upstream} | {args.ptype} |)"  # noqa: E501
        )
        if args.apply:
            README.write_text(rnew)
    else:
        print("  . README.md  (no change)")

    print()
    if args.apply:
        print(
            "Applied. Next: edit the new package's PKGBUILD, check.sh, update.sh."  # noqa: E501
        )
    else:
        print("Dry-run complete. Re-run with --apply to write changes.")


if __name__ == "__main__":
    main()
