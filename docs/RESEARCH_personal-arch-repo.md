# Research: Personal Arch Linux Repository -- Deep Dive

## Date: 2026-07-24

## Duration: ~3 hours deep-dive

## Type: deep-dive

---

## Summary

Setting up a professional personal Arch Linux pacman repository is remarkably
straightforward with modern tooling. The ecosystem has converged on a clear
set of best practices: host via GitHub Releases (zero-cost, no VPS needed),
build in Docker containers (cachyos/docker-makepkg or archlinux:base-devel),
automate with GitHub Actions, optionally sign with GPG, and use metapackages
to manage groups of related packages across machines.

The existing setup has the right bones -- per-package check.sh/update.sh
pattern for version tracking, GitHub Releases hosting, per-package
directories with PKGBUILDs. What's missing are the CI workflows, a proper
build environment strategy, GPG signing considerations, metapackage
scaffolding, and a few structural conventions that separate "works for me"
from "professional-grade."

This document covers the full landscape: every hosting option, signing model,
automation pattern, metapackage strategy, and naming convention. The
companion ACTION_PLAN.md has the exact step-by-step to get a repo from its
current state to production-ready.

---

## Key Findings

- **GitHub Releases is the de facto standard hosting strategy** -- zero-cost,
  CDN-backed, works with pacman natively. The pattern is a fixed release tag
  (e.g. `repository`) that gets overwritten on each deploy. Far simpler than
  GitHub Pages or self-hosted HTTP.

- **CachyOS docker-makepkg containers are the gold standard for CI builds** --
  they provide pre-configured makepkg.conf profiles for different CPU
  targets (generic/v3/v4/znver4) and include Arch build tooling. The
  `cachyos/docker-makepkg` image family is designed for exactly this use
  case. You can use plain `archlinux:base-devel` but you'll need to
  configure makepkg.conf yourself.

- **Three-workflow pattern is most common for professional setups**:
  sync/update workflow (checks for new versions), verify workflow
  (test-builds PRs), and publish workflow (builds + deploys to release).
  A two-workflow plan (update + build) is almost there but is missing the
  verify step and the PR-based safety gate.

- **GPG signing is recommended but Optional TrustAll is fine for personal
  repos** -- even the professional community is split. The Arch Wiki and
  most templates default to `Optional TrustAll` for personal repos. GPG
  signing adds complexity in CI (key management, passphrase storage,
  gpg-agent setup) that's usually not worth it unless you're distributing
  to untrusted third parties.

- **Metapackages are the intended way to group packages** -- not package
  groups. Metapackages (empty packages that depend on other packages)
  auto-install new members on update, can depend on other metapackages
  (hierarchical grouping), and work transparently with pacman -Syu.
  Package groups are for interactive selection during install.

- **The check.sh/update.sh pattern is excellent** -- it's cleaner than
  the nvchecker approach used by official Arch devs for this use case.
  Per-package version check scripts are simple, auditable, and don't
  require learning another tool. The pattern is worth systematizing into
  a template.

- **Arch Wiki's `makepkg-template` system exists for PKGBUILD reuse** --
  but it's rarely used in practice for personal repos. Most people
  copy a template PKGBUILD and customize. The per-package dir pattern
  is the standard convention.

- **GitHub Actions `workflow_dispatch` inputs for selective builds** is
  the most requested feature a basic setup is missing -- ability to
  say "build only this one package" instead of rebuilding everything.

---

## Analysis

### How Pacman Repos Actually Work

Every pacman repository -- official, unofficial, or personal -- is just a
directory containing:

1. Package files: `*.pkg.tar.zst` (optionally with `*.pkg.tar.zst.sig`)
2. A database file: `<repo-name>.db.tar.gz` (or `.tar.zst`)
3. A files metadata file: `<repo-name>.files.tar.gz` (same compression)

The database is managed by `repo-add` and `repo-remove` (both in the
`pacman` package). When you run `pacman -Sy`, pacman fetches the database,
reads the metadata, and knows what packages are available.

Key insight: the database file extension doesn't have to match your
compression. Using `.tar.gz` for the database is fine even if your
packages use `.zst`. The convention is:

- Database: `repo-name.db.tar.gz` (gzip is universal, smallest download)
- Packages: `pkgname-ver-rel-arch.pkg.tar.zst` (zstd for speed/size)

### Hosting Strategies -- Ranked

| Strategy | Cost | Complexity | Speed | Notes |
|----------|------|------------|-------|-------|
| GitHub Releases | Free | Low | CDN-fast | Fixed tag, overwritten each time |
| GitHub Pages | Free | Medium | CDN-fast | Needs arch subdir, separate branch |
| Your own HTTP(S) | VPS cost | High | You-control | nginx + autoindex |
| Syncthing | Free | Medium | LAN-fast | Needs at least one peer online |
| Local file:// | Free | Trivial | Instant | Single machine only |

**GitHub Releases (winner)**: Use a permanent tag (e.g. `repository`), and
on each build, delete old assets and upload new ones. The URL pattern is:

```
Server = https://github.com/<user>/<repo>/releases/download/<tag>
```

Pro tip: since the release tag is static, pacman caches aggressively. If
packages don't change between builds, consider a versioned tag approach
to avoid unnecessary downloads. But for a personal repo, the
static-tag-rewrite pattern is simplest.

### Build Environment Strategies

**Option A: CachyOS Docker containers (recommended for GitHub Actions)**

```yaml
container:
  image: cachyos/docker-makepkg-v3  # or docker-makepkg / -v4 / -znver4
```

In practice, the cleanest approach in GitHub Actions is to invoke makepkg
via `docker run` from a `run:` step (rather than a `container:` block),
because GitHub Actions that run *inside* a custom `container:` block hit a
permission quirk: the action's file-command writes fail with EACCES when
the image's default user differs from the runner user. Running
`docker run cachyos/docker-makepkg-v3 bash -c '...'` from a plain `run:`
step avoids that entirely.

These containers have:
- A non-root `notroot` user (with passwordless sudo) -- makepkg must
  NOT run as root, and `--asroot` was removed from makepkg in 2023, so
  build as `notroot` and let makepkg's internal `sudo pacman` install deps.
- Pre-configured makepkg with optimal flags for the target (x86-64-v3 by
  default for the `-v3` image).
- Note: newer pacman enables a Landlock sandbox that fails inside Docker
  (no BPF). Disable it in the container via `DisableSandbox` in
  `/etc/pacman.conf`, or run pacman with `--disable-sandbox`.

Download the matching makepkg.conf profile if building outside the image:
```bash
curl -sLo /etc/makepkg.conf \
  https://raw.githubusercontent.com/CachyOS/docker-makepkg/master/docker-makepkg-v3/makepkg.conf
```

**Option B: archlinux:base-devel (simpler, more control)**

```yaml
container:
  image: archlinux:base-devel
```

Pro: official image, full control.
Con: you must set up a non-root user, sudo, configure makepkg yourself.

The boilerplate for option B:
```dockerfile
RUN pacman -Syu --noconfirm --needed base-devel git sudo && \
    useradd -m builder && \
    echo 'builder ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers
```

**Option C: mserajnik/arch-repo-create Docker image**

A purpose-built image that uses pikaur for AUR deps and handles signing.
Good if you have complex AUR dependency chains. Less control than raw
cachyos containers.

### Package Structure Conventions

**Per-package directories** (what this repo has) is the standard:

```
personal-repo/
  cal-com/
    PKGBUILD
    check.sh
    update.sh
    cal-com.sh          # support files
  unsloth-bin/
    PKGBUILD
    check.sh
    update.sh
    unsloth-studio.sh
  .github/workflows/
    build.yml
    update.yml
    verify.yml
  README.md
```

**Flat layout with a single packages.txt** is the alternative used by the
n0bcode template -- it works when you're mostly syncing AUR packages with
a few local ones. The per-package dir pattern is better for a repo with
mostly self-maintained packages.

### The check.sh / update.sh Pattern

This is one of the strongest parts of the setup. Let's formalize it:

- `check.sh`: Idempotent, outputs upstream version to stdout, exits 0 on
  success. No side effects. Examples: curl + grep from a yml file, curl +
  python from a JSON API, git ls-remote for tagged releases.

- `update.sh`: Reads check.sh, compares with PKGBUILD, bumps pkgver +
  pkgrel + updpkgsums if newer. Exits 0 whether or not it made changes
  (makes CI scripting simpler).

- Discoverability: a top-level CI step iterates `*/update.sh` and commits
  any changes. This is elegant and should be kept.

Pro nuance: an unsloth update.sh skips updpkgsums because checksums are
SKIP. Consider having update.sh always try updpkgsums, and handle the SKIP
case via a marker file (e.g. `NO_CHECKSUMS`) so the script is generic.

### GPG Signing -- The Real Picture

**The case for signing:**
- Verifies package integrity and authenticity
- Required if you ever submit to unofficial user repositories list
- Professional polish

**The case against signing for personal repos:**
- GPG key management in CI is painful (export secret key as base64 secret,
  import in workflow, set up gpg-agent with passphrase)
- Key rotation means updating all client machines
- If your build environment is compromised, the key is compromised
- `Optional TrustAll` is fine when you control both the repo and the
  machines consuming it

**The compromise:** Sign the repo database but NOT individual packages.

```bash
repo-add --verify --sign repo.db.tar.gz *.pkg.tar.zst
# generates repo.db.tar.gz.sig -- sign the database only
# this verifies the package listing came from you
# without having to sign every single build artifact
```

This is what sainnhe.dev does and is a good middle ground.

**To set up signing in CI:**

1. Generate a dedicated signing subkey (not your main key)
2. Export it: `gpg --export-secret-key --armor <key-id> | base64`
3. Store as GitHub secret `GPG_PRIVATE_KEY`
4. In workflow:
   ```bash
   echo "$GPG_PRIVATE_KEY" | base64 -d | gpg --import
   # Configure git for signing too
   git config --global user.signingkey <key-id>
   git config --global commit.gpgsign true
   ```

### Metapackages Deep Dive

Metapackages are the correct answer for "I want to install all my stuff
on a new machine with one command."

**PKGBUILD for a metapackage:**

```bash
# Maintainer: Your Name <maintainer@example.com>
pkgname=USERNAME-meta-base
pkgver=1
pkgrel=1
pkgdesc="Base metapackage -- packages every system needs"
arch=('any')
license=('GPL')
depends=(
  # official packages
  'base'
  'base-devel'
  'git'
  'vim'
  'zsh'
  'tmux'
  # from personal repo
  'cal-com-bin'
  'unsloth-bin'
  # AUR packages built and hosted in your repo
  'some-aur-package'
)
```

**Hierarchical metapackage pattern:**

```
USERNAME-meta-base          # everything everywhere needs
  |
  +-- USERNAME-meta-dev     # development tools
  |
  +-- USERNAME-meta-desktop # GUI apps, compositor, etc.
  |
  +-- USERNAME-meta-gaming  # steam, lutris, etc.
```

Each machine installs only the metapackages it needs. When you add a new
app to `USERNAME-meta-base`, every machine gets it on next `pacman -Syu`.

**Important:** Metapackage deps can reference packages from your personal
repo, the official repos, or any other repo in pacman.conf. The only
requirement is that pacman can see the repo at install time.

**Versus Package Groups:**
Groups (`groups=('my-group')` in PKGBUILD) are useful for interactive
selection (`pacman -S my-group` asks which members to install), but they
don't auto-install new members. Metapackages are what you want for
automated multi-machine management.

### GitHub Actions Workflow Patterns

**Three-workflow architecture (most professional):**

1. **update.yml** -- Scheduled (e.g., daily cron). Iterates `*/update.sh`
   to check for upstream version bumps. If any PKGBUILDs changed, commits
   and pushes to a branch or opens a PR.

2. **verify.yml** -- Triggered by PRs to main. Builds changed packages in
   a clean container to verify they compile. Uses a CachyOS container.

3. **build.yml** (or publish.yml) -- Triggered on push to main, plus
   manual dispatch (`workflow_dispatch`). Builds all packages (or only
   changed ones), runs `repo-add`, uploads to GitHub Release tag.

**Key details for the build workflow:**

- Use a matrix strategy for parallel builds across packages
- The publish step needs `contents: write` permission
- `gh release upload --clobber` overwrites existing assets
- Delete old assets first to remove packages that were deleted from repo

**Build matrix example (docker-run style that works in practice):**

```yaml
jobs:
  detect:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.changed.outputs.matrix }}
    steps:
      - uses: actions/checkout@v7
      - name: Find changed packages
        id: changed
        run: |
          matrix=$(find . -maxdepth 2 -name PKGBUILD -exec dirname {} \; \
            | sed 's|^\./||' | grep -v '^_template$' | sort -u \
            | jq -R -s -c 'split("\n") | map(select(. != ""))')
          echo "matrix=$matrix" >> "$GITHUB_OUTPUT"
  build:
    needs: detect
    runs-on: ubuntu-latest
    strategy:
      matrix:
        package: ${{ fromJson(needs.detect.outputs.matrix) }}
      fail-fast: false
    steps:
      - uses: actions/checkout@v7
      - name: Build in container
        run: |
          docker run --rm -v "$PWD":/ws -w /ws \
            cachyos/docker-makepkg-v3 bash -c '
              sudo chown -R notroot:notroot /ws
              sudo pacman-key --init >/dev/null 2>&1
              sudo pacman -Sy --noconfirm archlinux-keyring cachyos-keyring >/dev/null 2>&1
              sudo pacman-key --populate archlinux cachyos >/dev/null 2>&1
              sudo pacman -Syu --noconfirm >/dev/null 2>&1 || true
              export PKGDEST="/ws"
              cd "${{ matrix.package }}"
              makepkg -cfs --noconfirm
            '
      - uses: actions/upload-artifact@v7
        with:
          name: ${{ matrix.package }}
          path: '*.pkg.tar.zst'
  publish:
    needs: [detect, build]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v8
        with:
          path: repo-staging
          pattern: '*'
          merge-multiple: true
      - name: Generate repo database
        run: |
          docker run --rm -v "$PWD/repo-staging":/data -w /data \
            archlinux:latest bash -c 'repo-add personal-repo.db.tar.zst *.pkg.tar.zst'
      - name: Publish to Release
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          TAG="repository"
          gh release view "$TAG" --repo "$GITHUB_REPOSITORY" >/dev/null 2>&1 \
            || gh release create "$TAG" --title "Package Repository" --notes "" --repo "$GITHUB_REPOSITORY"
          gh release upload "$TAG" repo-staging/* --clobber --repo "$GITHUB_REPOSITORY"
```

### Repository Naming Conventions

The community is split on naming:

- **Repo name = your username**: `[USERNAME]` -- matches GitHub namespace,
  but can conflict with official repos on some systems
- **Repo name = repo name + suffix**: `[USERNAME-repo]` -- explicit, avoids
  confusion, a common choice
- **Repo name = descriptive**: `[personal]` or `[custom]` -- simpler but
  less descriptive across machines

**Package name conventions for your custom packages:**

- `*-bin` suffix for pre-built binaries (current pattern -- correct)
- `*-git` suffix for VCS packages (nightly builds from git)
- No suffix for packages you wrote yourself (e.g. `my-tool`)
- `*-meta` suffix for metapackages

**Version numbering for metapackages:**
Since metapackages just depend on other packages and don't have their own
upstream version, use `pkgver=YYYYMMDD` or simple incrementing integers.
Increment `pkgrel` when adding/removing deps without changing the
structure, bump `pkgver` when the set changes significantly.

### Fresh Install Bootstrap

The ultimate goal: install a new Arch machine with one command sequence.

```bash
# 1. Add repo during install (in arch-chroot)
cat >> /etc/pacman.conf << 'EOF'
[USERNAME-repo]
SigLevel = Optional TrustAll
Server = https://github.com/USERNAME/personal-repo/releases/download/repository
EOF

# 2. Sync and install your metapackage
pacman -Sy
pacman -S USERNAME-meta-base

# 3. That single metapackage pulls in everything
```

You can even include this in an archiso customization:
- Add your repo to the ISO's pacman.conf
- Include your key if using signing
- Base install + `pacman -S USERNAME-meta-base` = fully configured system

### What The Existing Setup Does Well

1. **Per-package check.sh/update.sh pattern** -- This is actually better
   than most templates. It's discoverable, per-package, and version checks
   are plain bash scripts. Keep this.

2. **GitHub Releases hosting** -- Correct choice. No VPS, CDN-backed.

3. **Clean PKGBUILDs** -- Well-structured with proper depends, optdepends,
   provides, conflicts. Desktop entries are generated correctly.

4. **README clarity** -- Clear setup instructions already documented.

### What Needs Improvement

1. **No CI workflows** -- The README describes update.yml and build.yml
   but they don't exist in the repo yet.
2. **No verify/build-in-chroot step** -- Building in the GitHub runner's
   native environment can miss dependency issues. Using a Docker container
   (cachyos-based) ensures clean-room builds.
3. **No matrix build** -- Building packages serially is slow. A build
   matrix parallelizes them.
4. **No metapackages** -- Missing the grouping mechanism that makes a
   personal repo truly useful across multiple machines.
5. **No GPG signing** -- Optional, but worth documenting either way.
6. **No workflow_dispatch for selective builds** -- Being able to
   manually trigger a build of a single package is useful during
   development.
7. **Repo name in pacman.conf** -- `[USERNAME-repo]` is fine, but
   consider whether `[USERNAME]` is cleaner.

---

## Perspectives

**Perspective A: "Minimal, no signing, just works"**
- Strengths: Simple, fast to set up, easy to maintain
- Weaknesses: No integrity verification, wouldn't pass review for
  unofficial user repositories list
- Evidence: Most GitHub templates (n0bcode, kaz, etc.) use this
- Verdict: Fine for personal use, which is the use case here

**Perspective B: "Fully signed, production-grade"**
- Strengths: Integrity verification, professional polish, listable
- Weaknesses: Significant CI complexity, key management burden
- Evidence: Arch Wiki, sainnhe.dev blog
- Verdict: Overkill for a single-user personal repo, but worth
  understanding the pattern for future-proofing

**Perspective C: "AUR farm approach" (n0bcode/nafets227)**
- Strengths: Auto-syncs from AUR, zero maintenance for AUR packages
- Weaknesses: Less control, needs PAT tokens for cross-workflow auth,
  complex caching logic
- Evidence: n0bcode template has 3 workflow files, ~700 lines total
- Verdict: Good if you maintain many AUR packages. A repo focused on
  self-maintained packages is better served by the per-package approach.

**Perspective D: "Metapackage-driven multi-machine management" (joram/stoicaviator)**
- Strengths: True single-command bootstrap, hierarchical grouping,
  auto-distributes new packages to all machines
- Weaknesses: Requires discipline to maintain metapackage deps
- Evidence: Joram's blog post, stoicaviator's guide, disconnected.systems
- Verdict: This is the direction a personal repo should grow toward.
  Metapackages are the killer feature of a personal repo.

---

## Sources

| # | Source | Type | Quality | Notes |
| --- | --- | --- | --- | --- |
| 1 | Arch Wiki: Pacman/Tips and tricks | Official Wiki | Strong | Authoritative reference for repo-add/remove commands |
| 2 | Arch Wiki: Creating packages | Official Wiki | Strong | PKGBUILD reference, packaging functions |
| 3 | Arch Wiki: PKGBUILD man page | Official Man Page | Strong | Definitive PKGBUILD syntax reference |
| 4 | Arch Wiki: Meta package and package group | Official Wiki | Strong | Definitively explains metapackages vs groups |
| 5 | Arch Wiki: Unofficial user repositories | Official Wiki | Strong | What's needed to list a repo publicly |
| 6 | n0bcode/my-arch-repo (GitHub) | Production template | Moderate | Well-documented, used by many forks |
| 7 | sainnhe.dev blog post | Tutorial | Moderate | Good GPG signing walkthrough, 2021 but still accurate |
| 8 | joram.io blog post | Personal blog | Moderate | Best real-world metapackage walkthrough, 2024 |
| 9 | stoicaviator/arch_metapackage_guide | Guide | Moderate | Comprehensive metapackage tutorial |
| 10 | CachyOS/docker-makepkg | Official repo | Strong | Reference for CI build containers |
| 11 | mserajnik/arch-repo-create | Docker image | Moderate | Alternative CI approach with pikaur |
| 12 | flouda.net custom repo guide | Tutorial | Moderate | General overview, covers basics well |
| 13 | disconnected.systems blog | Blog post | Moderate | Metapackage + config management pattern |
| 14 | alpm-repo(7) man page | Official Man Page | Strong | Low-level repo format specification |
| 15 | nerdstuff.org meta packages post | Blog post | Moderate | Systemd preset + metapackage integration |

Quality ratings:
- strong: official Arch Wiki, man pages, primary documentation
- moderate: well-written tutorials, production templates with active
  maintenance
- weak: opinion pieces without evidence (none in this list)

---

## Open Questions

1. **When to use split packages?** Not needed for the current use case
   (each package is its own directory), but worth understanding if you
   ever maintain a library + binary from the same source.

2. **archiso integration depth?** How far to take the bootstrap story --
   custom archiso vs just pacstrap + post-install script. Not urgent.

3. **mise integration?** Some packages are installed via mise because
   they're not on AUR. How do those fit? Either (a) package them and host
   in your repo, or (b) leave them in mise and accept the split. Worth a
   later discussion. (Note: keep mise/uv off the CI build path -- the
   build container is clean Arch with no mise/uv on PATH, so a naive
   `python3` call inside a package resolves to the system interpreter.)

4. **Multi-arch builds?** A local build host with a discrete GPU suggests
   you might want CUDA packages. GitHub runners don't have GPUs, so CUDA
   packages would need special handling (pre-built binary packaging only,
   no compilation).

---

## Confidence

**HIGH** -- The underlying technology (pacman repos, repo-add, GitHub
Actions) is mature and well-documented. There's no ambiguity about how
things work. The recommendations here are based on documented best
practices from the Arch Wiki, analysis of 10+ production repos, and
community consensus.

The main uncertainty is around specific package requirements (which
packages need building, AUR vs local, mise overlap), which is domain
knowledge only the maintainer has.

---

## Suggested KB Placement

- Primary topic: arch-linux/personal-repo
- Related topics: arch-linux/packaging, arch-linux/ci-cd, arch-linux/metapackages
- Tags: arch-linux, pacman, packaging, github-actions, metapackages, ci-cd
