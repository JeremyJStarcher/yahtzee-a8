# Determine repo root relative to the including Makefile's location
REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)

# Hostname for venv selection (matches build.py's _venv_dir scheme)
HOSTNAME := $(shell hostname 2>/dev/null || echo unknown)
ifeq ($(HOSTNAME),)
HOSTNAME := unknown
endif

# Venv paths
#VENV_DIR := $(REPO_ROOT)/venv/hosts/venv-$(HOSTNAME)
VENV_DIR := $(REPO_ROOT)/venv/venv-ours
VENV_BIN := $(VENV_DIR)/bin
VENV_PYTHON := $(VENV_BIN)/python

# Load the venv environment by prepending its bin dir to PATH
# and setting VIRTUAL_ENV (tools like pip check this)
export PATH := $(VENV_BIN):$(PATH)
export VIRTUAL_ENV := $(VENV_DIR)
