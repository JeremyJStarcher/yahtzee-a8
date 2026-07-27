SHELL := /bin/bash

ROOT := $(CURDIR)
VENV_HOME := $(ROOT)/../venv/hosts
VENV_DIR := $(VENV_HOME)/venv-$(shell hostname)
VENV_PY := $(VENV_DIR)/bin/python
RUFF := $(VENV_DIR)/bin/ruff
PYREFLY := $(VENV_DIR)/bin/pyrefly

CLOCK_HZ ?= 1000000
INSTRUCTIONS_PER_BATCH ?= 2000
SCREEN_SCALE ?= 4

# Defaults used by plain `make run`.
VIDEO_BACKEND ?= bitmap
REFRESH_HZ ?= 60

# Backend-specific defaults.
TEXT_REFRESH_HZ ?= 60
BITMAP_REFRESH_HZ ?= 30

# Add extra emulator options from the command line, for example:
#
#   make run-text EXTRA_RUN_ARGS='--text-font-family "DejaVu Sans Mono"'
#
EXTRA_RUN_ARGS ?=

BASE_RUN_ARGS = \
	--clock-hz $(CLOCK_HZ) \
	--instructions-per-batch $(INSTRUCTIONS_PER_BATCH) \
	--screen-scale $(SCREEN_SCALE) \
	$(EXTRA_RUN_ARGS)

.PHONY: \
	all \
	run \
	run-text \
	run-bitmap \
	run-gfx \
	lint \
	format \
	typecheck \
	infer \
	clean \
	ensure-venv \
	build-bios

# This Makefile requires a Python virtual environment at:
#
#   ../venv/hosts/venv-<hostname>
#
ensure-venv:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating virtualenv at $(VENV_DIR)..."; \
		mkdir -p "$(VENV_HOME)"; \
		python3 -m venv "$(VENV_DIR)" || { \
			echo "Failed to create virtualenv"; \
			rm -rf "$(VENV_DIR)"; \
			exit 1; \
		}; \
		echo "Installing requirements..."; \
		"$(VENV_PY)" -m pip install --upgrade pip setuptools wheel || true; \
		"$(VENV_PY)" -m pip install -r "$(ROOT)/../venv/requirements.txt" || { \
			echo "Failed to install requirements"; \
			rm -rf "$(VENV_DIR)"; \
			exit 1; \
		}; \
	else \
		echo "Virtualenv already exists at $(VENV_DIR)"; \
	fi

all: run

# Configurable default runner.
run: | ensure-venv build-bios
	"$(VENV_PY)" fcon.py $(BASE_RUN_ARGS) \
		--video-backend "$(VIDEO_BACKEND)" \
		--refresh-hz "$(REFRESH_HZ)"

# Native Tk text renderer.
run-text: | ensure-venv build-bios
	"$(VENV_PY)" fcon.py $(BASE_RUN_ARGS) \
		--video-backend text \
		--refresh-hz "$(TEXT_REFRESH_HZ)"

# Original bitmap renderer.
run-bitmap: | ensure-venv build-bios
	"$(VENV_PY)" fcon.py $(BASE_RUN_ARGS) \
		--video-backend bitmap \
		--refresh-hz "$(BITMAP_REFRESH_HZ)"

# Short alias for the bitmap renderer.
run-gfx: run-bitmap

build-bios:
	@echo "Building BIOS..."
	$(MAKE) -C "$(ROOT)/bios"

lint: | ensure-venv
	"$(RUFF)" check . --fix
	"$(PYREFLY)" check .

infer: | ensure-venv
	"$(PYREFLY)" infer .

format: | ensure-venv
	"$(RUFF)" format .

typecheck: | ensure-venv
	"$(PYREFLY)" check .

clean:
	rm -f *.pyc
	$(MAKE) -C "$(ROOT)/bios" clean
