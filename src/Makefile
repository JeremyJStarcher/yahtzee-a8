SHELL := /bin/bash

ROOT := $(CURDIR)
VENV_DIR := $(ROOT)/../venv/.venv
VENV_PY := $(VENV_DIR)/bin/python
RUFF := $(VENV_DIR)/bin/ruff
PYREFLY := $(VENV_DIR)/bin/pyrefly

RESOURCE_DIR := $(ROOT)/resource-builder
ATASM := $(ROOT)/../../code/atasm
ATARI800 := $(ROOT)/../../code/atari800

A8DISK := $(ROOT)/../disks/a8.atr
A8BIN := AUTORUN.SYS
RESOURCE_OUTPUT := generated/strings.m65 generated/ram.m65 generated/state.m65

.PHONY: all run run-disk lint test build-resources assemble clean ensure-venv

# This Makefile REQUIRES a Python virtualenv at `venv/.venv`.

ensure-venv:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating virtualenv at $(VENV_DIR)..."; \
		mkdir -p $(ROOT)/../venv; \
		python3 -m venv $(VENV_DIR) || { echo "Failed to create virtualenv"; rm -rf $(VENV_DIR); exit 1; }; \
		echo "Installing requirements..."; \
# Upgrade base packaging tools: pip=installer, setuptools/wheel=needed to build/install many packages \
		$(VENV_PY) -m pip install --upgrade pip setuptools wheel || true; \
		$(VENV_PY) -m pip install -r $(ROOT)/../venv/requirements.txt || { echo "Failed to install requirements"; rm -rf $(VENV_DIR); exit 1; }; \
	else \
		echo "Virtualenv already exists at $(VENV_DIR)"; \
	fi

all: run

run: $(A8BIN)
	$(ATARI800) $(A8BIN)

run-disk: $(A8BIN)
	$(ATARI800) $(A8DISK)

$(A8BIN): hw_a8.m65 $(RESOURCE_OUTPUT) | ensure-venv
	rm -f $(A8BIN)
	$(ATASM) -x${A8DISK} -g/tmp/file.lst -o${A8BIN} ./hw_a8.m65

generated/strings.m65 generated/ram.m65 generated/state.m65: $(RESOURCE_DIR)/resource_builder.py | ensure-venv
	$(VENV_PY) $(RESOURCE_DIR)/resource_builder.py

lint: | ensure-venv
	$(RUFF) format $(RESOURCE_DIR)
	$(RUFF) check $(RESOURCE_DIR) --fix
	$(PYREFLY) check $(RESOURCE_DIR)

test: | ensure-venv
	PYTHONPATH=$(RESOURCE_DIR) $(VENV_PY) -m unittest discover -s $(RESOURCE_DIR)/tests -p "test_*.py"

build-resources: $(RESOURCE_OUTPUT)


clean:
	rm -f $(A8BIN)
	rm -rf generated
	rm -f a8*
