# Root Makefile for the personal Arch repo.
# Wraps scripts/ so packages can be managed without remembering flags.
# Each target mirrors a tool; add new targets here as tools are added.
#
# Common flows:
#   make new PKG=foo LANG=go      # scaffold a Go package + wire it in
#   make check                    # what's stale? (runs every check.sh)
#   make bump                     # bump ALL stale packages via their update.sh
#   make bump PKG=unsloth-bin     # bump just one package
#   make sync                     # refresh pacman db (paru -Syy / fallback)
#   make validate                 # makepkg --nobuild per package
#   make lint                     # wiring/consistency guard
#   make all                      # check + validate + lint
#
# NOTE: `make` / `make all` is read-only -- it reports stale packages but does
# NOT bump them or touch VCS. Bumping requires a commit, so it is a separate
# `make bump` step you run when you actually want to advance pkgver.
#
# sync honors $PKG_MANAGER (e.g. paru); if unset it falls back to
# paru -> yay -> pacman.

SCRIPTS := scripts
PKG ?=
LANG ?=
QUIET ?=

ifneq ($(QUIET),)
  QFLAG := --quiet
endif

.PHONY: all new check bump validate lint sync help

all: check validate lint sync


new:
	@if [ -z "$(PKG)" ]; then echo "usage: make new PKG=<name> [LANG=go|rust|bin]"; exit 1; fi
	python3 $(SCRIPTS)/new_package.py $(PKG) --lang $(LANG) --apply

n: new

check:
	python3 $(SCRIPTS)/bump_check.py $(QFLAG)

c: check

# Bump packages to their latest upstream version by running each package's
# update.sh. update.sh is a no-op when already current, so running over all
# packages is safe. Does NOT commit/push -- that's a VCS step you do after.
bump:
	@if [ -n "$(PKG)" ]; then \
		echo "Bumping $(PKG)..."; \
		bash $(SCRIPTS)/../$(PKG)/update.sh || exit 1; \
	else \
		echo "Bumping all stale packages via their update.sh..."; \
		fail=0; \
		for d in */; do \
			[ "$$d" = "_template/" ] && continue; \
			[ -f "$$d/update.sh" ] || continue; \
			echo "--- $$d"; \
			bash "$$d/update.sh" || fail=1; \
		done; \
		exit $$fail; \
	fi

# Refresh the local pacman database (the "paru -Syy" step) using $PKG_MANAGER
# or a detected fallback (paru/yay/pacman).
sync:
	bash $(SCRIPTS)/sync_db.sh

s: sync

validate:
	python3 $(SCRIPTS)/validate_all.py $(QFLAG)

v: validate

lint:
	python3 $(SCRIPTS)/repo_lint.py $(QFLAG)

l: lint

help:
	@echo "Targets:"
	@echo "  make new PKG=<name> [LANG=go|rust|bin]  scaffold + wire a package"
	@echo "  make check                               report stale packages"
	@echo "  make bump [PKG=<name>]                   bump stale pkgver via update.sh"
	@echo "  make sync                                refresh pacman db (PKG_MANAGER/fallback)"
	@echo "  make validate                            makepkg --nobuild per package"
	@echo "  make lint                                consistency guard"
	@echo "  make all                                 check + validate + lint"
	@echo "  QUIET=1 make <target>                    suppress non-error output"

h: help
