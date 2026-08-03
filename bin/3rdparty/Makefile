include $(dir $(lastword $(MAKEFILE_LIST)))Makefile.mk

WASI_SDK_PATH ?= $(HOME)/.local/wasi-sdk

.PHONY: all cc65 clean
all:
	@echo "Using venv: $(VENV_DIR)"
	@echo "All."

cc65:
	WASI_SDK_PATH=$(WASI_SDK_PATH) bash build-cc65/build_cc65_wasi.sh

clean:
	$(MAKE) -C cc65 clean 2>/dev/null || true
	rm -rf cc65/wrk cc65/bin
	rm -rf $(REPO_ROOT)/wasi
