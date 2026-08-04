include $(dir $(lastword $(MAKEFILE_LIST)))Makefile.mk

WASI_SDK_PATH ?= $(HOME)/.local/wasi-sdk
EMSDK_PATH     ?= $(HOME)/emsdk

.PHONY: all cc65 reinette reinette-native reinette-wasi chips chips-wasi clean
all: cc65 reinette chips
	@echo "Using venv: $(VENV_DIR)"
	@echo "All."

cc65:
	WASI_SDK_PATH=$(WASI_SDK_PATH) bash build-cc65/build_cc65_wasi.sh

reinette: reinette-native reinette-wasi
	cp reinette-II-plus/apple2.wasm ../wasi
	cp reinette-II-plus/apple2_host.py ../wasi


reinette-native:
	$(MAKE) -C reinette-II-plus reinetteII+

reinette-wasi:
	bash -l -c 'source "$(EMSDK_PATH)/emsdk_env.sh" >/dev/null 2>&1 && \
		$(MAKE) -C reinette-II-plus -f Makefile.wasi wasi'

chips: chips-wasi
	cp chips-wasi/vic20.wasm ../wasi
	cp chips-wasi/c64.wasm ../wasi
	cp chips-wasi/vic20_host.py ../wasi
	cp chips-wasi/c64_host.py ../wasi
	cp chips-wasi/commodore_host.py ../wasi

chips-wasi:
	bash -l -c 'source "$(EMSDK_PATH)/emsdk_env.sh" >/dev/null 2>&1 && \
		$(MAKE) -C chips-wasi all'

clean:
	$(MAKE) -C cc65 clean 2>/dev/null || true
	rm -rf cc65/wrk cc65/bin
	rm -rf $(REPO_ROOT)/wasi
	$(MAKE) -C reinette-II-plus clean 2>/dev/null || true
	rm -f reinette-II-plus/wasi.wasm reinette-II-plus/wasi.js reinette-II-plus/wasi.data
	$(MAKE) -C chips-wasi clean 2>/dev/null || true
	rm -f chips-wasi/wasi.wasm chips-wasi/wasi.js chips-wasi/wasi.data
