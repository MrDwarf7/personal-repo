# Action Plan: Personal Arch Repo -- Production-Ready Setup

## Companion to docs/RESEARCH_personal-arch-repo.md

This document is an exact, actionable roadmap to take a personal-repo from
its current state to a professional, self-maintaining setup. Every step is
concrete and scriptable.

---

## Phase 1: CI Infrastructure

### Step 1: Create the GitHub Actions workflows

Create `.github/workflows/` with three workflow files:

**1a. `update.yml`** -- Scheduled daily check for upstream version bumps.

```yaml
name: Update packages

on:
  schedule:
    - cron: '0 6 * * *'   # daily at 6am UTC
  workflow_dispatch: {}     # manual trigger

env:
  GH_TOKEN: ${{ github.token }}

jobs:
  check-updates:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0

      - name: Check for updates
        run: |
          updated=false
          for script in */update.sh; do
            dir=$(dirname "$script")
            echo "=== Checking $dir ==="
            cd "$dir"
            bash update.sh
            cd ..
          done

      - name: Commit changes if any
        run: |
          if ! git diff --quiet; then
            git config user.name "repo-bot"
            git config user.email "bot@example.com"
            git add -A
            git commit -m "chore: auto-update packages [$(date +%Y-%m-%d)]"
            git push
          fi
```

**1b. `verify.yml`** -- Test-build changed packages in a clean container.

```yaml
name: Verify packages

on:
  pull_request:
    paths:
      - '*/PKGBUILD'
      - '*/*.sh'
      - '*.txt'

jobs:
  verify:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        package:
          - cal-com
          - unsloth-bin
      fail-fast: false
    steps:
      - uses: actions/checkout@v7
      - name: Test build in cachyos container
        run: |
          docker run --rm -v "$PWD":/ws -w /ws \
            cachyos/docker-makepkg-v3 bash -c '
              sudo chown -R notroot:notroot /ws
              sudo pacman-key --init >/dev/null 2>&1
              sudo pacman -Sy --noconfirm archlinux-keyring cachyos-keyring >/dev/null 2>&1
              sudo pacman-key --populate archlinux cachyos >/dev/null 2>&1
              sudo pacman -Syu --noconfirm >/dev/null 2>&1 || true
              cd "${{ matrix.package }}" && makepkg -cfs --noconfirm
            '
```

Note: run makepkg via `docker run` from a `run:` step (not a `container:`
block) to avoid the EACCES file-command permission quirk that GitHub
Actions hit inside custom containers.

**1c. `build.yml`** -- Build all + publish to GitHub Release.

This is the big one. See the RESEARCH doc for the full matrix +
publish workflow skeleton. Key elements:

- Matrix build across all package directories
- CachyOS container with matching makepkg profile (run via `docker run`)
- `repo-add` to generate the pacman database
- `gh release upload --clobber` to publish
- `workflow_dispatch` with package selector for manual builds

### Step 2: Configure GitHub repository settings

Required permissions for Actions to write releases:

1. Settings > Actions > General
2. Workflow permissions: "Read and write permissions"
3. Check "Allow GitHub Actions to create and approve pull requests"
4. Save

### Step 3: Set up Docker-based build environment

A local build host runs Arch, but CI runs on GitHub's x86_64 runners.
Use the `cachyos/docker-makepkg-v3` image which matches modern x86-64
> Haswell (2013). The `-v3` image targets x86-64-v3 CPU features.

If you want to build locally for testing:

```bash
# Build a package in a clean CachyOS container
docker run --rm -v $PWD/cal-com:/pkg cachyos/docker-makepkg-v3

# Or with archlinux:base-devel
docker run --rm -v $PWD/cal-com:/pkg archlinux:base-devel \
  bash -c "pacman -Syu --noconfirm base-devel && \
           useradd -m b && chown -R b:b /pkg && \
           su b -c 'cd /pkg && makepkg -cfs'"
```

---

## Phase 2: Package Infrastructure

### Step 4: Create a package template

Create a template directory structure that all packages follow:

```bash
mkdir _template
```

**Template PKGBUILD:**

```bash
# Maintainer: Your Name <maintainer@example.com>
# Contributor: <upstream author if different>

pkgname=PACKAGE_NAME
pkgver=0.0.0
pkgrel=1
pkgdesc="Human-readable description"
arch=('x86_64')
url="https://upstream-project.org"
license=('custom: commercial' OR 'GPL' OR 'MIT' etc.)
depends=()
optdepends=()
provides=()
conflicts=()
options=('!strip' if pre-built binary)

source=("url-to-source")
sha256sums=()
# if dynamic version, use check.sh/update.sh with SKIP checksums

package() {
  # Install to $pkgdir
  # Follow FHS: /usr/bin, /usr/share, /etc, /opt for large apps
}
```

**Template check.sh:**

```bash
#!/bin/bash
# Outputs the latest upstream version to stdout
# Exit 0 = version available, Exit 1 = could not determine
set -euo pipefail

# Method A: GitHub releases
# curl -sfL https://api.github.com/repos/owner/repo/releases/latest \
#   | grep '"tag_name":' | sed -E 's/.*"v?([0-9.]+)".*/\1/'

# Method B: AppImage/latest-linux.yml
# curl -sfL "https://download.todesktop.com/APPID/latest-linux.yml" \
#   | grep '^version:' | awk '{print $2}'

# Method C: PyPI
# curl -sfL "https://pypi.org/pypi/PACKAGE/json" \
#   | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])"

# Method D: Static URL with version in path
# curl -sfIL "https://example.com/download/thing-latest.tar.gz" \
#   | grep -oP 'thing-\K[0-9.]+(?=\.tar\.gz)' | head -1
```

**Template update.sh:**

```bash
#!/bin/bash
# Bumps pkgver if upstream has a newer version.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PKGBUILD="$DIR/PKGBUILD"

current=$(grep -m1 '^pkgver=' "$PKGBUILD" | cut -d= -f2)
upstream=$("$DIR/check.sh") || { echo "Could not determine upstream version"; exit 0; }

if [ "$upstream" = "$current" ]; then
  echo "Already up to date ($current)"
  exit 0
fi

echo "Bumping $current -> $upstream"
sed -i "s/^pkgver=.*/pkgver=${upstream}/" "$PKGBUILD"
sed -i "s/^pkgrel=.*/pkgrel=1/" "$PKGBUILD"

# Recompute checksums unless sources are SKIP or a NO_CHECKSUMS marker exists.
if [ ! -f "$DIR/NO_CHECKSUMS" ] \
   && grep -qE '^sha[0-9]*sums=' "$PKGBUILD" \
   && ! grep -q 'SKIP' "$PKGBUILD"; then
  ( cd "$DIR" && updpkgsums )
fi
```

### Step 5: Formalize existing packages

Existing packages are already well-structured. Just ensure:

- `cal-com-bin`: The AppImage extraction + perms fix is solid. Consider
  adding `.desktop` file validation
- `unsloth-bin`: The install.sh download + launcher pattern is correct
  for this kind of package

**Recommended additions for unsloth-bin:**
- Add `$pkgname.install` file with post-install messaging about first-run
  setup (installing python deps)
- Add a `NO_CHECKSUMS` marker file so update.sh can be generic

---

## Phase 3: Metapackages

### Step 6: Create metapackage structure

Create a `meta/` directory (or keep them alongside other packages):

```
meta/
  USERNAME-meta-base/
    PKGBUILD       # depends: base, base-devel, git, vim, cal-com-bin, etc.
  USERNAME-meta-dev/
    PKGBUILD       # depends: rust, go, docker, etc.
  USERNAME-meta-desktop/
    PKGBUILD       # depends: hyprland, waybar, etc.
```

**USERNAME-meta-base PKGBUILD:**

```bash
# Maintainer: Your Name <maintainer@example.com>
pkgname=USERNAME-meta-base
pkgver=1
pkgrel=1
pkgdesc="Metapackage: base packages needed on every system"
arch=('any')
url="https://github.com/USERNAME/personal-repo"
license=('GPL')
depends=(
  # official repos
  'base'
  'base-devel'
  'git'
  'zsh'
  'tmux'
  'htop'
  'neovim'
  'ripgrep'
  'fd'
  'fzf'
  # personal repo
  'cal-com-bin'
  'unsloth-bin'
)
```

**For metapackages, no check.sh or update.sh needed** -- they don't
have upstream versions. Just bump pkgver when you restructure deps.

---

## Phase 4: Fresh Install Bootstrap

### Step 7: Document the one-liner install

Update your README with the full bootstrap script:

```bash
#!/bin/bash
# Bootstrap a new Arch install with your packages

# Add the repo
cat >> /etc/pacman.conf << 'EOF'

[USERNAME-repo]
SigLevel = Optional TrustAll
Server = https://github.com/USERNAME/personal-repo/releases/download/repository
EOF

# Update and install
pacman -Sy
pacman -S USERNAME-meta-base
# Optionally:
pacman -S USERNAME-meta-dev USERNAME-meta-desktop
```

---

## Phase 5: GPG Signing (Optional)

### Step 8: Set up signing if you want it

Skip this unless you specifically want signed packages. If you do:

1. Create a dedicated subkey for package signing
2. Export as base64-encoded GitHub secret `GPG_PRIVATE_KEY`
3. Add GPG_PASSPHRASE secret if key has a passphrase
4. Add to build workflow:
   ```bash
   echo "$GPG_PRIVATE_KEY" | base64 -d | gpg --batch --import
   echo "$GPG_PASSPHRASE" | gpg --batch --passphrase-fd 0 --sign /dev/null
   makepkg --sign ...
   repo-add --verify --sign ...
   ```
5. Add pacman-key import to README:
   ```bash
   sudo pacman-key --recv-keys <your-key-id>
   sudo pacman-key --lsign-key <your-key-id>
   ```

**Decision:** For personal use, `Optional TrustAll` is perfectly
fine. Only add signing if you plan to share the repo publicly.

---

## Phase 6: Ongoing Maintenance

### Step 9: Package update workflow

Adding a new package:

1. Copy template dir: `cp -r _template my-new-pkg/`
2. Write PKGBUILD, check.sh, update.sh
3. Push to main -- workflows pick it up automatically
4. (Optional) Add metapackage dep if it's a base package

Removing a package:

1. Delete the directory and push
2. The build workflow will rebuild the repo database without it
3. Update metapackage deps if needed

### Step 10: CI optimization ideas

- **Skipping unchanged packages**: In the build workflow, compare git diff
  against main to only rebuild changed packages. Saves CI minutes.

- **Caching**: Use `actions/cache` for builder's pacman cache to speed up
  installs of common build deps.

- **Parallelism**: The matrix strategy already parallelizes. For 10+
  packages, this matters more.

- **Manual build of specific package**: Via `workflow_dispatch` inputs:
  ```yaml
  workflow_dispatch:
    inputs:
      package:
        description: 'Package to build (leave empty for all)'
        required: false
        type: string
  ```

---

## Summary: Before vs After

| Area | Current | Target |
|------|---------|--------|
| CI workflows | None exist | update.yml + verify.yml + build.yml |
| Build environment | Native runner | CachyOS Docker container |
| Build parallelism | Serial | Matrix across packages |
| Metapackages | None | USERNAME-meta-base + optional extras |
| GPG signing | Not documented | Optional, documented |
| Package template | Ad-hoc | Formal _template dir |
| Bootstrap flow | Manual steps | Single pacman command |
| Selective builds | Not possible | workflow_dispatch input |
| Version checking | Per-package scripts (excellent!) | Keep as-is |

---

## First Actions to Take Right Now

1. Create `.github/workflows/update.yml` with the daily check script
2. Create `.github/workflows/build.yml` with matrix + release publish
3. Create `_template/` with PKGBUILD, check.sh, update.sh stubs
4. Create `meta/USERNAME-meta-base/` with a basic PKGBUILD
5. Push everything and verify the workflows run
6. Test install from your repo on a fresh machine or VM
