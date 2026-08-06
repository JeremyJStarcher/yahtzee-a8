# Makefile — Build Atari800 as a pure-WASI headless module (no SDL2)
#
# Renders into a raw 336x240 RGBA framebuffer in linear WASM memory that the
# Python host reads via wasmtime and displays with pygame.
#
# Usage:
#   bash -l -c 'source ~/emsdk/emsdk_env.sh && make'
#
# Output:
#   atari800.wasm   - Atari 800XL/XE standalone WASI module

EMSDK_DIR = $(HOME)/emsdk
EMCC = $(EMSDK_DIR)/upstream/emscripten/emcc

# The Atari800 2.2.1 core lives in the Atari800Win-PLus tree.
ATARI_SRC = ../Atari800Win-PLus/Atari800/src

# -D_DEFAULT_SOURCE exposes POSIX decls (gettimeofday, mkstemp, M_PI ...) that
# strict -std=c11 (__STRICT_ANSI__) would otherwise hide in wasi-libc.
# -D_snprintf=snprintf: the Windows-oriented core calls the MSVC-only
# _snprintf() unconditionally in screen.c; map it to the C99 snprintf().
# -DWASI_EMBED_ROMS: enables the Atari800_LoadImage() fallback that serves
# the ROMs from arrays embedded by gen_roms.py (emcc STANDALONE_WASM cannot
# open files - no path_open import in this Emscripten build).
CFLAGS = -Wall -Wextra -std=c11 -D_DEFAULT_SOURCE -D_snprintf=snprintf -DWASI_EMBED_ROMS

WASI_FLAGS = \
	-sSTANDALONE_WASM=1 \
	-sINITIAL_MEMORY=134217728 \
	-sALLOW_MEMORY_GROWTH=0 \
	-O3

# Core sources (no pokeysnd/mzpokeysnd/sndsave: sound disabled in milestone 1)
SRCS = \
	$(ATARI_SRC)/afile.c \
	$(ATARI_SRC)/antic.c \
	$(ATARI_SRC)/atari.c \
	$(ATARI_SRC)/binload.c \
	$(ATARI_SRC)/cartridge.c \
	$(ATARI_SRC)/cassette.c \
	$(ATARI_SRC)/colours.c \
	$(ATARI_SRC)/colours_external.c \
	$(ATARI_SRC)/colours_ntsc.c \
	$(ATARI_SRC)/colours_pal.c \
	$(ATARI_SRC)/compfile.c \
	$(ATARI_SRC)/cpu.c \
	$(ATARI_SRC)/cycle_map.c \
	$(ATARI_SRC)/devices.c \
	$(ATARI_SRC)/esc.c \
	$(ATARI_SRC)/gtia.c \
	$(ATARI_SRC)/input.c \
	$(ATARI_SRC)/log.c \
	$(ATARI_SRC)/memory.c \
	$(ATARI_SRC)/monitor.c \
	$(ATARI_SRC)/pbi.c \
	$(ATARI_SRC)/pia.c \
	$(ATARI_SRC)/pokey.c \
	$(ATARI_SRC)/remez.c \
	$(ATARI_SRC)/rtime.c \
	$(ATARI_SRC)/screen.c \
	$(ATARI_SRC)/sio.c \
	$(ATARI_SRC)/statesav.c \
	$(ATARI_SRC)/util.c \
	atari800-wasi.c \
	cfg.c \
	ui.c

# Exported functions the Python host calls.
EXPORTS = "_wasi_init","_wasi_tick","_wasi_keydown","_wasi_keyup","_wasi_fb_ptr","_wasi_fb_width","_wasi_fb_height","_wasi_fb_raw_ptr","_wasi_fb_raw_width","_wasi_fb_raw_height","_wasi_screen_cols","_wasi_screen_rows","_wasi_screen_text","_wasi_insert_disk","_malloc","_free"

.PHONY: all clean

all: atari800.wasm

# Regenerate atari800_roms.h from the ROM images if it is missing/stale.
ROM_XL = $(ATARI_SRC)/../../Distribution/Rom/ATARIXL.ROM
atari800_roms.h: gen_roms.py $(ROM_XL)
	python3 gen_roms.py

atari800.wasm: $(SRCS) config.h cfg.h ui.h atari800_roms.h
	$(EMCC) $(SRCS) $(CFLAGS) $(WASI_FLAGS) \
		-I. -I$(ATARI_SRC) \
		-sEXPORTED_FUNCTIONS='[$(EXPORTS)]' \
		-o $@

clean:
	rm -f atari800.wasm atari800_roms.h
