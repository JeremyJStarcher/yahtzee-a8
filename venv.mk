# venv.mk — Shared Python virtual environment for the project.
#
# Include this from any Makefile that needs the project Python venv:
#
#     include ../venv.mk    # adjust path to reach the project root
#
# Provides:
#   VENV_PY    — path to the venv Python interpreter
#   VENV_DIR   — path to the venv directory
#   ensure-venv — target that creates the venv if missing

_PROJ_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VENV_HOME := $(_PROJ_ROOT)/venv/hosts
VENV_DIR := $(VENV_HOME)/venv-$(shell hostname)
VENV_PY := $(VENV_DIR)/bin/python

.PHONY: ensure-venv

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
		"$(VENV_PY)" -m pip install -r "$(_PROJ_ROOT)/venv/requirements.txt" || { \
			echo "Failed to install requirements"; \
			rm -rf "$(VENV_DIR)"; \
			exit 1; \
		}; \
	else \
		echo "Virtualenv already exists at $(VENV_DIR)"; \
	fi
