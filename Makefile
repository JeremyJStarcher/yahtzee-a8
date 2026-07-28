SHELL := /bin/bash

SRC_DIR := $(CURDIR)/src

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


