SHELL := /bin/bash

ROOT := $(CURDIR)
VENV_DIR := $(ROOT)/../venv/.venv
VENV_PY := $(VENV_DIR)/bin/python
RUFF := $(VENV_DIR)/bin/ruff
PYREFLY := $(VENV_DIR)/bin/pyrefly

.PHONY: all run lint format typecheck infer clean ensure-venv build-bios

# This Makefile REQUIRES a Python virtualenv at `../venv/.venv`.

ensure-venv:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating virtualenv at $(VENV_DIR)..."; \
		mkdir -p $(ROOT)/../venv; \
		python3 -m venv $(VENV_DIR) || { echo "Failed to create virtualenv"; rm -rf $(VENV_DIR); exit 1; }; \
		echo "Installing requirements..."; \
		$(VENV_PY) -m pip install --upgrade pip setuptools wheel || true; \
		$(VENV_PY) -m pip install -r $(ROOT)/../venv/requirements.txt || { echo "Failed to install requirements"; rm -rf $(VENV_DIR); exit 1; }; \
	else \
		echo "Virtualenv already exists at $(VENV_DIR)"; \
	fi

all: run

run: | ensure-venv build-bios
	$(VENV_PY) fcon.py

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
