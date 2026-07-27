# Packaging Rust projects for this repo (Arch guidelines)

Guidance for when a Rust crate gets added to this personal repo. Same model as
the Go packages: **build from source** in the CachyOS `docker-makepkg`
container via `build.yml`. No `-bin` re-host unless the only option is a
prebuilt deliverable.

## Source of truth

- Arch wiki: <https://wiki.archlinux.org/title/Rust_package_guidelines>
- AUR submission rules: <https://wiki.archlinux.org/title/AUR_submission_guidelines>

## Conventions

### Naming
- `pkgname` = the generated binary name, all lowercase. Only crate *bins* get
  packaged -- do NOT package library-only crates.
- Multiple binaries: use the upstream crate name as `pkgname`.
- If you must ship a prebuilt deliverable (no source path), append `-bin`
  (e.g. `foo-bin`) and use `options=('!strip')` where needed.

### Source
- Prefer a tagged source archive (GitHub tarball) or crates.io:
      source=("$pkgname-$pkgver.tar.gz::https://static.crates.io/crates/$pkgname/$pkgname-$pkgver.crate")
- crates.io tarballs often lack test/license assets -- supplement with the
  GitHub archive if you need them.

### Depends / makedepends
- `makedepends=(cargo)` -- cargo/rustc come from the `rust` package; depend on
  `cargo` directly. Nightly-only projects use `cargo-nightly`.
- Most Rust binaries are statically linked against crates, so `depends` is
  usually empty except glibc/libgcc when linking the system libc:
      depends=(gcc-libs glibc)
- Add system libs if the crate links native C/C++ (see Unbundling below).

### prepare() -- fetch offline
    prepare() {
        export RUSTUP_TOOLCHAIN=stable
        cargo fetch --locked --target "$CARCH"
    }
- `--locked` honors `Cargo.lock` for reproducible builds.
- `--target "$CARCH"` (or your host tuple) fetches only what the target needs.
- If upstream does NOT keep `Cargo.lock` synced, add `cargo update` before
  fetch (then the build is no longer fully reproducible).
- `RUSTUP_TOOLCHAIN=stable` guards against a user's non-default toolchain when
  NOT building in a chroot. In this repo's CachyOS container it is harmless.

### build()
    build() {
        export RUSTUP_TOOLCHAIN=stable
        export CARGO_TARGET_DIR=target
        cargo build --frozen --release --all-features
    }
- `--frozen` = `--locked --offline` (uses the fetch cache, reproducible).
- `--release` = optimized build.
- `--all-features` (or `--features a,b`) -- pick per project.
- `CARGO_TARGET_DIR=target` keeps output under the package dir.
- LTO issue: GCC-built C/C++ deps can fail to link under LTO. Fixes:
  remove bundled libs, or disable `lto` in the affected crate's build
  (binary still LTO'd by Rust's own optimizer).

### check()
    check() {
        export RUSTUP_TOOLCHAIN=stable
        cargo test --frozen --all-features
    }
- Do NOT use `--release` in tests (disables overflow checks / `debug_assert!`).
- Cargo **workspace** (`[workspace]` in Cargo.toml)? add `--workspace` so all
  members are tested.

### package()
- Single binary:
      install -Dm0755 -t "$pkgdir/usr/bin/" "target/release/$pkgname"
- Multiple binaries:
      find target/release -maxdepth 1 -executable -type f \
          -exec install -Dm0755 -t "$pkgdir/usr/bin/" {} +
- Custom license (MIT etc.):
      install -Dm644 LICENSE "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
- `cargo install` alternative (only when you must install extra assets like a
  man page and there's no other way):
      package() {
          export RUSTUP_TOOLCHAIN=stable
          cargo install --no-track --frozen --all-features \
              --root "$pkgdir/usr/" --path .
      }
  `--no-track` is mandatory -- without it cargo writes `/usr/.crates.toml`
  and `/usr/.crates2.json`, which pollute the package.

### Unbundling C/C++ libraries (security + reproducibility)
Inspect `cargo tree --all-features` and each `-sys` crate's `build.rs` for
env vars that switch off vendored static linking. Common toggles:

| Crate            | Native dep | Toggle                                        |
| ---------------- | ---------- | --------------------------------------------- |
| jemalloc-sys     | jemalloc   | `JEMALLOC_OVERRIDE=/usr/lib/libjemalloc.so`   |
| lcms2-sys        | lcms2      | `LCMS2_LIB_DIR=/usr/lib`                      |
| libgit2-sys      | libgit2    | `LIBGIT2_NO_VENDOR=1`                         |
| libsqlite3-sys   | sqlite     | `LIBSQLITE3_SYS_USE_PKG_CONFIG=1`             |
| libssh2-sys      | libssh2    | `LIBSSH2_SYS_USE_PKG_CONFIG=1`                |
| openssl-sys      | openssl    | `OPENSSL_NO_VENDOR=1`                         |
| zstd-sys         | zstd       | `ZSTD_SYS_USE_PKG_CONFIG=1`                   |

Add the matching system lib to `depends` when you set one of these.

### Complete PKGBUILD template (from the wiki)
    # Maintainer: Firstname Lastname <email@example.org>
    pkgname=
    pkgver=
    pkgrel=1
    pkgdesc=''
    url=''
    license=()
    makedepends=('cargo')
    depends=()
    arch=('x86_64' 'aarch64')
    source=()
    sha256sums=()

    prepare() {
        export RUSTUP_TOOLCHAIN=stable
        cargo fetch --locked --target "$CARCH"
    }
    build() {
        export RUSTUP_TOOLCHAIN=stable
        export CARGO_TARGET_DIR=target
        cargo build --frozen --release --all-features
    }
    check() {
        export RUSTUP_TOOLCHAIN=stable
        cargo test --frozen --all-features
    }
    package() {
        install -Dm0755 -t "$pkgdir/usr/bin/" "target/release/$pkgname"
    }

### Version source & update.sh (same pattern as Go packages)
- Parse the latest GitHub release tag / crates.io version in `check.sh`.
- `update.sh` bumps `pkgver`, resets `pkgrel=1`, and runs `updpkgsums`.

### .SRCINFO
- Not required for this binary repo (pacman consumes the built `.db.tar.zst`
  directly). Do NOT commit `.SRCINFO`.

## How this differs from the repo's `-bin` packages
- `cal-com-bin` / `unsloth-bin` download a prebuilt artifact and wrap it in a
  launcher script. A Rust/Go source package compiles inside the container and
  installs the binary to `/usr/bin` directly -- no `/opt` layout, no `.sh`
  launcher, no `!strip`.
- Both still use the same `check.sh`/`update.sh` version-bump machinery and
  are auto-discovered by `build.yml` / `update.yml` / `verify.yml`.
