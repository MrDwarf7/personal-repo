# personal-repo

Prebuilt pacman packages for software not (well) served by the AUR, hosted on
GitHub Releases and kept up to date automatically.

## Features

- Prebuilt `-bin` packages for apps missing or stale in the AUR
- Daily upstream version checks via per-package `check.sh` / `update.sh`
- Clean-room builds in CachyOS containers (x86-64-v3 tuned)
- Publish to a GitHub Release tagged `repository`, consumed by pacman natively
- No GPG key management required (`Optional TrustAll`)

## Requirements

| What    | Need                                    |
| ------- | --------------------------------------- |
| OS      | Arch Linux (or derivative using pacman) |
| CPU     | x86-64-v3 or newer (Haswell+, 2013+)    |
| Access  | GitHub Releases (public, CDN-backed)    |
| Signing | None -- `Optional TrustAll`             |

## Install

Add the repo to `/etc/pacman.conf`:

    [mrdwarf7-repo]
    SigLevel = Optional TrustAll
    Server = https://github.com/MrDwarf7/personal-repo/releases/download/repository

Note: the bare `Server` URL returns 404 in a browser -- that's normal GitHub
behavior (no directory listing at that path). pacman appends the database
name (`personal-repo.db`) automatically, so the repo resolves correctly on
`pacman -Syu`. The release tagged `repository` is what serves the packages.

Then sync and install:

    sudo pacman -Syu
    sudo pacman -S <whatever the pkg is>

## Packages

| Package     | Upstream    | Type                           |
| ----------- | ----------- | ------------------------------ |
| cal-com-bin | Cal.com     | Electron AppImage (ToDesktop)  |
| unsloth-bin | Unsloth     | Python venv (PyTorch + UI)     |
| xeet        | melqtx/xeet | Go source build (cgo + libX11) |

## How it works

Three GitHub Actions workflows keep the repo self-maintaining:

- `update.yml` -- daily cron. Runs every `*/update.sh`; commits any version
  bumps it finds.
- `verify.yml` -- on pull requests. Test-builds changed packages in a clean
  CachyOS container (no publish).
- `build.yml` -- on push (and manual `workflow_dispatch`). Builds changed
  packages in parallel, runs `repo-add`, and uploads the database + packages
  to the `repository` release.

## Add a package

Copy the scaffold and fill it in:

    cp -r _template my-app
    # edit my-app/PKGBUILD, my-app/check.sh, my-app/update.sh
    # see cal-com/ for a complete real example

Push to the default branch -- `update.yml` and `build.yml` pick it up
automatically. No workflow edits required (the build matrix discovers
`*/PKGBUILD` and excludes `_template`).

## Notes

- Build artifacts (`*.pkg.tar.zst`, `*.AppImage`, `pkg/`, `src/`) are
  git-ignored and never committed.
- GPG signing is intentionally not used. The repo is single-user and
  `Optional TrustAll` is sufficient. If you later share this repo, add
  database signing (`repo-add --sign`) and a `pacman-key` trust step.
- CI builds run in a clean `cachyos/docker-makepkg-v3` container with no
  `mise` or `uv` on PATH, so naive `python3` calls inside packages resolve to
  the system interpreter. Locally, deactivate `mise` before running
  `check.sh` / `makepkg` if it shadows `python3` on your machine.
- Metapackages (`mrdwarf7-meta-*`) are planned to enable one-command
  bootstrap of a new machine.
