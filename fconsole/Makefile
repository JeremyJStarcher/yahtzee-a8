SHELL := /bin/bash

ROOT := $(CURDIR)
VENV_HOME := $(ROOT)/../venv/hosts
VENV_DIR := $(VENV_HOME)/venv-$(shell hostname)
VENV_PY := $(VENV_DIR)/bin/python
RUFF := $(VENV_DIR)/bin/ruff
PYREFLY := $(VENV_DIR)/bin/pyrefly

CYCLES_PER_FRAME ?= 8000
SCREEN_SCALE ?= 2

.PHONY: all run lint format typecheck infer clean ensure-venv build-bios

# This Makefile REQUIRES a Python virtualenv at `../venv/hosts/.venv-<hostname>`.

ensure-venv:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating virtualenv at $(VENV_DIR)..."; \
		mkdir -p $(VENV_HOME); \
		python3 -m venv $(VENV_DIR) || { echo "Failed to create virtualenv"; rm -rf $(VENV_DIR); exit 1; }; \
		echo "Installing requirements..."; \
		$(VENV_PY) -m pip install --upgrade pip setuptools wheel || true; \
		$(VENV_PY) -m pip install -r $(ROOT)/../venv/requirements.txt || { echo "Failed to install requirements"; rm -rf $(VENV_DIR); exit 1; }; \
	else \
		echo "Virtualenv already exists at $(VENV_DIR)"; \
	fi

all: run

RUN_ARGS ?= \
	--cycles-per-frame $(CYCLES_PER_FRAME) \
	--screen-scale $(SCREEN_SCALE)

run: | ensure-venv build-bios
	$(VENV_PY) fcon.py $(RUN_ARGS)

build-bios:
	@echo "Building BIOS..."
	$(MAKE) -C $(ROOT)/bios

lint: | ensure-venv
	$(RUFF) check . --fix
	$(PYREFLY) check .

infer: | ensure-venv
	$(PYREFLY) infer .

format: | ensure-venv
	$(RUFF) format .

typecheck: | ensure-venv
	$(PYREFLY) check .

clean:
	rm -f *.pyc
	$(MAKE) -C $(ROOT)/bios clean

