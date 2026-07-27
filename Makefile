# Root Makefile for the personal Arch repo.
# Wraps scripts/ so packages can be managed without remembering flags.
# Each target mirrors a tool; add new targets here as tools are added.
#
# Common flows:
#   make new PKG=foo LANG=go      # scaffold a Go package + wire it in
#   make check                    # what's stale? (runs every check.sh)
#   make validate                 # makepkg --nobuild per package
#   make lint                     # wiring/consistency guard
#   make all                      # check + validate + lint

SCRIPTS := scripts
PKG ?=
LANG ?=
QUIET ?=

ifneq ($(QUIET),)
  QFLAG := --quiet
endif

.PHONY: all new check validate lint help

all: check validate lint

new:
	@if [ -z "$(PKG)" ]; then echo "usage: make new PKG=<name> [LANG=go|rust|bin]"; exit 1; fi
	python3 $(SCRIPTS)/new_package.py $(PKG) --lang $(LANG) --apply

check:
	python3 $(SCRIPTS)/bump_check.py $(QFLAG)

validate:
	python3 $(SCRIPTS)/validate_all.py $(QFLAG)

lint:
	python3 $(SCRIPTS)/repo_lint.py $(QFLAG)

help:
	@echo "Targets:"
	@echo "  make new PKG=<name> [LANG=go|rust|bin]  scaffold + wire a package"
	@echo "  make check                               report stale packages"
	@echo "  make validate                            makepkg --nobuild per package"
	@echo "  make lint                                consistency guard"
	@echo "  make all                                 check + validate + lint"
	@echo "  QUIET=1 make <target>                    suppress non-error output"
