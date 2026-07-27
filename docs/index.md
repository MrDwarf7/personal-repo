# docs/ index

A quick-reference table of contents for the docs directory. Start here to find
the document you need -- use the keyword search sections below rather than
opening every file at once. When you add or retire a doc, update the table
(it is the single source of truth for discovery).

## Table of contents

| Topic | File | What it is |
| ------ | ---- | ----------- |
| Personal repo research deep-dive | [RESEARCH_personal-arch-repo.md](RESEARCH_personal-arch-repo.md) | 3h deep-dive: hosting, signing, CI patterns, metapackages |
| Personal repo action plan | [ACTION_PLAN_personal-arch-repo.md](ACTION_PLAN_personal-arch-repo.md) | Step-by-step from current state to production-ready |
| Packaging Go projects | [PACKAGING-Go.md](PACKAGING-Go.md) | Arch Go PKGBUILD conventions (PIE/hardening flags, cgo deps, source build) |
| Packaging Rust projects | [PACKAGING-Rust.md](PACKAGING-Rust.md) | Arch Rust PKGBUILD conventions (cargo fetch/build, unbundling -sys crates) |

## Quick search by use case

- "how do I package a Go app here?"  -> PACKAGING-Go.md
- "how do I package a Rust crate here?" -> PACKAGING-Rust.md
- "why is the repo set up this way?" -> RESEARCH_personal-arch-repo.md
- "what are the exact steps to finish the repo?" -> ACTION_PLAN_personal-arch-repo.md

## Quick search by keyword

- PIE, CGO_* , GOFLAGS, -linkmode=external, libX11, xeet -> PACKAGING-Go.md
- cargo fetch, --frozen, --locked, -sys, unbundling, openssl-sys -> PACKAGING-Rust.md
- GitHub Releases, cachyos/docker-makepkg, GPG, metapackage, SigLevel -> RESEARCH_personal-arch-repo.md / ACTION_PLAN_personal-arch-repo.md
