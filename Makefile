SHELL := /bin/bash

SRC_DIR := $(CURDIR)/src

.PHONY: all run lint test build-resources assemble clean

all: run

%:
	$(MAKE) -C $(SRC_DIR) $@

run:
	$(MAKE) -C $(SRC_DIR) run
