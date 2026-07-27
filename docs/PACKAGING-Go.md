# Packaging Go projects for this repo (Arch guidelines)

This repo builds from **source** for Go projects (the binary is compiled inside
the CachyOS `docker-makepkg` container by `build.yml`). This is the opposite of
the `-bin` packages in here (cal-com-bin, unsloth-bin), which ship prebuilt
upstream artifacts. A source build is the correct call for Go per the Arch wiki:
vendored modules + static-ish binary, no reason to re-host a tarball.

## Source of truth

- Arch wiki: <https://wiki.archlinux.org/title/Go_package_guidelines>
- AUR submission rules: <https://wiki.archlinux.org/title/AUR_submission_guidelines>

## Conventions this repo enforces

### Naming
- `pkgname` = the program name, all lowercase (`xeet`, not `go-xeet`). The
  `go-` prefix is only for libs "strongly coupled to the Go ecosystem". Apps
  ship under their own name.
- If you ever package a Go *library* you depend on, use `go-<modulename>`.

### Module handling (go modules)
- Prefer upstreams that ship `go.mod`. In `prepare()` set
  `GOPATH="$srcdir"` and run `go mod download -modcacherw` so the module
  graph is cached into the build dir. `build()`/`check()` then build offline.
- If upstream has no `go.mod`, init one in prepare:
  `go mod init "${url#https://}"; go mod tidy`. (Unreproducible -- file an
  upstream issue instead.)

### Build flags (CRITICAL)
Go does **not** pass `CFLAGS`/`LDFLAGS` to its C toolchain automatically. For
PIE + RELRO + other hardening you must export the `CGO_*` vars and `GOFLAGS`
explicitly. The repo's canonical block (mirrors the wiki sample):

    export CGO_CPPFLAGS="${CPPFLAGS}"
    export CGO_CFLAGS="${CFLAGS}"
    export CGO_CXXFLAGS="${CXXFLAGS}"
    export CGO_LDFLAGS="${LDFLAGS}"
    export GOFLAGS="-buildmode=pie -trimpath -ldflags=-linkmode=external -mod=readonly -modcacherw"
    export GOPATH="$srcdir"

- `-buildmode=pie`    -> PIE binary hardening
- `-trimpath`          -> reproducible builds (no build paths in binary)
- `-mod=readonly`      -> never mutates go.mod/go.sum during build
- `-modcacherw`        -> writeable module cache (default is read-only)
- `-linkmode=external` -> uses the system linker so `LDFLAGS` (RELRO etc.)
  actually take effect.

WARNING: if the upstream `Makefile` overrides `GOFLAGS` or omits these flags,
either patch it or bypass it and call `go build` directly. The wiki is
explicit: "It is up to the packager to verify the build flags are passed
correctly." For xeet, `make build` drops `-buildmode=pie`/`-linkmode=external`,
so the PKGBUILD calls `go build` directly with the flags above.

### cgo / native dependencies
If the project uses cgo (xeet does, via `golang.design/x/clipboard` -> X11):
- `makedepends` needs `base-devel` (provides gcc for cgo) and the native lib
  with headers (`libx11`).
- Add the runtime lib to `depends` if the binary links/dlopens it at runtime
  (xeet dlopens `libX11.so`; Wayland paths use `wl-clipboard`).
- The nix `default.nix` / `flake.nix` of the upstream project is the fastest
  way to discover the real native deps -- read those before guessing.

### Output / install
- Build into a local dir, then install the single binary:
      go build -o "$pkgname" .
      install -Dm755 "$pkgname" "$pkgdir/usr/bin/$pkgname"
- Install the license to `/usr/share/licenses/$pkgname/` and any docs to
  `/usr/share/doc/$pkgname/`. MIT/0BSD/etc. live under `licenses/`.
- xeet ships `LICENSE` (MIT) + `README.md` + `THIRD_PARTY_NOTICES.md`.

### check()
- `go test ./...` in `check()`. Safe in the clean room because xeet gates its
  network/live tests behind `XEET_LIVE_*` env vars (they `t.Skip` otherwise).
- Keep `check()` non-fatal-friendly: it should pass offline. Do not enable the
  live env vars in the PKGBUILD.

### Version source & update.sh
- Upstream tags: `vX.Y.Z`. The GitHub auto-tarball extracts to
  `xeet-X.Y.Z/`, which is exactly what makepkg wants, so:
      source=("$pkgname-$pkgver.tar.gz::https://github.com/<owner>/<repo>/archive/refs/tags/v$pkgver.tar.gz")
  Note the `v` is concatenated into the URL, NOT into `$pkgver`.
- `check.sh` prints the latest release tag with the `v` stripped
  (`sed -E 's/.*"v?([0-9][0-9.]*[0-9])".*/\1/'`).
- `update.sh` bumps `pkgver` + resets `pkgrel=1`, then runs `updpkgsums` to
  recompute the tarball sha256. This matches the repo's other packages.

### .SRCINFO
- `build.yml` does not auto-generate `.SRCINFO` (only the AUR requires it;
  this is a binary repo consumed by pacman). Do NOT commit `.SRCINFO`.

## xeet specifics (reference package)
- `pkgname=xeet`, `pkgver=0.1.9`, MIT, `arch=('x86_64' 'aarch64')`.
- `makedepends=(go git base-devel libx11)`, `depends=(glibc libx11 wl-clipboard)`.
- Build calls `go build -o xeet .` directly (not `make`) to keep the hardening
  flags. `check()` runs `go test ./...`.
- Source tarball sha256 is pinned and recomputed by `update.sh` on bump.
