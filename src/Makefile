SHELL := /bin/bash

ROOT := $(CURDIR)
VENV_DIR := $(ROOT)/venv/.venv
VENV_PY := $(VENV_DIR)/bin/python
RUFF := $(VENV_DIR)/bin/ruff
PYREFLY := $(VENV_DIR)/bin/pyrefly

RESOURCE_DIR := $(ROOT)/resource-builder
ATASM := $(ROOT)/../../code/atasm
ATARI800 := $(ROOT)/../../code/atari800

.PHONY: all run lint test build-resources assemble clean

# This Makefile REQUIRES a Python virtualenv at `venv/.venv`.
ifeq ($(wildcard $(VENV_PY)),)
$(error Missing virtualenv at $(VENV_DIR). Create it with: python3 -m venv $(VENV_DIR))
endif

all: run

run: yahtzee.65o
	$(ATARI800) yahtzee.65o

yahtzee.65o: yahtzee.m65 $(RESOURCE_DIR)/resource_builder.py
	rm -f yahtzee.65o
	rm -rf generated
	rm -f a8*
	$(MAKE) lint
	$(VENV_PY) $(RESOURCE_DIR)/resource_builder.py
	$(ATASM) -xd2.atr -g/tmp/file.lst ./yahtzee.m65

lint:
	$(RUFF) format $(RESOURCE_DIR)
	$(RUFF) check $(RESOURCE_DIR) --fix
	$(PYREFLY) check $(RESOURCE_DIR)

test:
	PYTHONPATH=$(RESOURCE_DIR) $(VENV_PY) -m unittest discover -s $(RESOURCE_DIR)/tests -p "test_*.py"

build-resources: yahtzee.65o

assemble:
	$(ATASM) -xd2.atr -g/tmp/file.lst ./yahtzee.m65

clean:
	rm -f yahtzee.65o
	rm -rf generated
	rm -f a8*
