# Makefile — Build VIC-20 and C64 as pure-WASI headless modules (no SDL2)
#
# Renders into raw RGBA32 framebuffers in linear WASM memory that the
# Python hosts read via wasmtime and display with pygame.
#
# Usage:
#   source ~/emsdk/emsdk_env.sh && make
#
# Output:
#   vic20.wasm   - VIC-20 standalone WASI module
#   c64.wasm     - C64 standalone WASI module

EMSDK_DIR = $(HOME)/emsdk
EMCC = $(EMSDK_DIR)/upstream/emscripten/emcc

# -D_DEFAULT_SOURCE exposes M_PI etc. in the musl math.h which the
# strict -std=c11 (__STRICT_ANSI__) would otherwise hide (m6581.h SID needs M_PI).
CFLAGS = -Wall -Wextra -std=c11 -D_DEFAULT_SOURCE
WASI_FLAGS = \
	-sSTANDALONE_WASM=1 \
	-sINITIAL_MEMORY=67108864 \
	-sALLOW_MEMORY_GROWTH=0 \
	-O3

# Exported functions the Python host calls.
# Each name is quoted so EXPORTS expands to a valid JSON array for
# -sEXPORTED_FUNCTIONS (see the recipe: '["$(EXPORTS)"]').
EXPORTS = "_wasi_init","_wasi_tick","_wasi_keydown","_wasi_keyup","_wasi_fb_ptr","_wasi_fb_width","_wasi_fb_height","_wasi_fb_raw_ptr","_wasi_fb_raw_width","_wasi_fb_raw_height","_wasi_screen_cols","_wasi_screen_rows","_wasi_screen_text","_wasi_insert_disk","_wasi_load_prg","_malloc","_free"

.PHONY: all clean

all: vic20.wasm c64.wasm

vic20.wasm: vic20-wasi.c vic20_roms.h
	$(EMCC) $< $(CFLAGS) $(WASI_FLAGS) \
		-sEXPORTED_FUNCTIONS='[$(EXPORTS)]' \
		-o $@

c64.wasm: c64-wasi.c c64_roms.h
	$(EMCC) $< $(CFLAGS) $(WASI_FLAGS) \
		-sEXPORTED_FUNCTIONS='[$(EXPORTS)]' \
		-o $@

clean:
	rm -f vic20.wasm c64.wasm
