SHELL := /bin/bash

include venv.mk

.DEFAULT_GOAL := all

SRC_DIR := $(CURDIR)/src
PYTHON ?= $(VENV_PY)

# --- WASI SDK toolchain (maintainer-only) ---
WASI_SDK_PATH ?= $(HOME)/.local/wasi-sdk
BUILD_SCRIPT := bin/3rdparty/build-cc65/build_cc65_wasi.sh

# --- Existing yahtzee-a8 targets ---
.PHONY: all run lint test build-resources assemble clean

all: run
%:
	$(MAKE) -C $(SRC_DIR) $@

clean:
	cd fconsole && make clean

run:
	$(MAKE) -C $(SRC_DIR) run

bios-list:
	$(MAKE) clean
	./concat_files.sh fconsole/bios/

fcon-list:
	$(MAKE) clean
	./concat_files.sh fconsole

devtools-list:
	$(MAKE) clean
	./concat_files.sh dev-tools/

# --- WASI cc65 toolchain targets ---
.PHONY: build-tools clean-tools cc65-test cc65-test-clean cc65-test-suite

build-tools:
	WASI_SDK_PATH=$(WASI_SDK_PATH) bash $(BUILD_SCRIPT)

clean-tools:
	rm -rf bin/wasi

cc65-test:
	$(MAKE) -C bin/3rdparty/cc65-asm-tests/bios PYTHON=$(PYTHON)

cc65-test-clean:
	$(MAKE) -C bin/3rdparty/cc65-asm-tests/bios clean

cc65-test-suite:
	$(PYTHON) bin/3rdparty/cc65-tests/test_runner.py
	$(PYTHON) bin/3rdparty/cc65-tests/test_cc65_pipeline.py
