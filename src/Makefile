SHELL := /bin/bash

ROOT := $(CURDIR)
VENV_DIR := $(ROOT)/../venv/.venv
VENV_PY := $(VENV_DIR)/bin/python
RUFF := $(VENV_DIR)/bin/ruff
PYREFLY := $(VENV_DIR)/bin/pyrefly

RESOURCE_DIR := $(ROOT)/resource-builder
ATASM := $(ROOT)/../../code/atasm
ATARI800 := $(ROOT)/../../code/atari800

.PHONY: all run lint test build-resources assemble clean ensure-venv

# This Makefile REQUIRES a Python virtualenv at `venv/.venv`.

ensure-venv:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating virtualenv at $(VENV_DIR)..."; \
		mkdir -p $(ROOT)/../venv; \
		python3 -m venv $(VENV_DIR) || { echo "Failed to create virtualenv"; rm -rf $(VENV_DIR); exit 1; }; \
		echo "Installing requirements..."; \
# Upgrade base packaging tools: pip=installer, setuptools/wheel=needed to build/install many packages \
		$(VENV_PY) -m pip install --upgrade pip setuptools wheel || true; \
		$(VENV_PY) -m pip install -r ../venv/requirements.txt || { echo "Failed to install requirements"; rm -rf $(VENV_DIR); exit 1; }; \
	else \
		echo "Virtualenv already exists at $(VENV_DIR)"; \
	fi

all: run

run: yahtzee.65o
	$(ATARI800) yahtzee.65o

yahtzee.65o: yahtzee.m65 $(RESOURCE_DIR)/resource_builder.py | ensure-venv
	rm -f yahtzee.65o
	rm -rf generated
	rm -f a8*
	$(MAKE) lint
	$(VENV_PY) $(RESOURCE_DIR)/resource_builder.py
	$(ATASM) -xd2.atr -g/tmp/file.lst ./yahtzee.m65

lint: | ensure-venv
	$(RUFF) format $(RESOURCE_DIR)
	$(RUFF) check $(RESOURCE_DIR) --fix
	$(PYREFLY) check $(RESOURCE_DIR)

test: | ensure-venv
	PYTHONPATH=$(RESOURCE_DIR) $(VENV_PY) -m unittest discover -s $(RESOURCE_DIR)/tests -p "test_*.py"

build-resources: yahtzee.65o

assemble:
	$(ATASM) -xd2.atr -g/tmp/file.lst ./yahtzee.m65

clean:
	rm -f yahtzee.65o
	rm -rf generated
	rm -f a8*
