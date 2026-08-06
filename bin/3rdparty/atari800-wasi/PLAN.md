# atari800-wasi: Atari 800/XL/XE WASI Emulator (Milestone 1 - Boot to BASIC)

## Goal

A standalone `atari800.wasm` module that boots an Atari 800XL/XE to the Atari
BASIC `READY.` prompt, driven by a Python host using pygame via `wasmtime-py`.
The video is rendered into a linear RGBA framebuffer in WASM memory that the
host reads and displays with pygame.  No SDL2, no audio (milestone 1).

The port wraps the Atari800 2.2.1 core bundled in
`../Atari800Win-PLus/Atari800/src/` — the same "library-ized" core used by
Atari800Win-PLus — exactly mirroring the chips-wasi / reinette-II-plus WASI
pattern already in this workspace.

## Python Environment

```
/home/jjs/Projects/atari800/yahtzee-a8/venv/hosts/venv-flat-line/bin/python
```
Packages: `wasmtime`, `pygame` (both confirmed present).

## Emscripten

```bash
source ~/emsdk/emsdk_env.sh
emcc --version
```

## ROM Files

Source: `../Atari800Win-PLus/Distribution/Rom/`

| Machine | File | Role | Size |
|---------|------|------|------|
| 800XL/XE | `ATARIXL.ROM` | XL/XE OS ROM | 16384 B |
| 800XL/XE | `ATARIBAS.ROM` | Atari BASIC | 8192 B |
| 800 (OS-B) | `ATARIOSB.ROM` | OS-B ROM | 10240 B |

The ROMs are exposed to the module through a WASI preopened directory: the
host maps the guest path `/roms` onto the `Distribution/Rom` directory.  The
glue sets `CFG_xlxe_filename = /roms/ATARIXL.ROM` and
`CFG_basic_filename = /roms/ATARIBAS.ROM` before `Atari800_Initialise()`.
If the `/roms` directory is not preopened (or the files are missing) the core
automatically falls back to its built-in EmuOS (`emuos_mode` defaults to 1).

## Directory

```
atari800-wasi/
├── PLAN.md            <- this file
├── config.h           # WASI core configuration (no SDL/sound/etc.)
├── cfg.h / cfg.c      # CFG_*_filename globals + no-op config load/save
├── ui.h / ui.c        # minimal UI stubs (UI_Run etc.)
├── atari800-wasi.c    # WASI glue: PLATFORM_*, wasi_* exports, framebuffer
├── Makefile           # emcc build rule -> atari800.wasm
└── atari800_host.py   # wasmtime binding + pygame renderer (interactive & headless)
```

Core sources are compiled **in place** from `../Atari800Win-PLus/Atari800/src/`
(unchanged).  `pokeysnd.c`, `mzpokeysnd.c` and `sndsave.c` are **excluded**
from the milestone-1 build: with `SOUND` (and friends) undefined the core has
no references to them.

Built:
```
└── atari800.wasm      # standalone WASI module
```

## Exported API (atari800-wasi.c)

| Export | Description |
|--------|-------------|
| `void wasi_init(void)` | set ROM paths, `Atari800_Initialise()`, `Atari800_Coldstart()` |
| `void wasi_tick(void)` | run one Atari frame; blit visible 336x240 to RGBA framebuffer |
| `int wasi_keydown(int pg_key, int unicode_char)` | inject key press (pygame key + unicode) |
| `int wasi_keyup(int pg_key, int unicode_char)` | inject key release |
| `int wasi_fb_ptr(void)` | address of the RGBA framebuffer in linear memory |
| `int wasi_fb_width(void)` | 336 |
| `int wasi_fb_height(void)` | 240 |
| `int wasi_fb_raw_ptr(void)` | address of `Screen_atari` (384x240 color-index buffer) |
| `int wasi_fb_raw_width(void)` | 384 |
| `int wasi_fb_raw_height(void)` | 240 |
| `int wasi_insert_disk(...)` | stub, returns 0 (future .atr support) |
| `_malloc`, `_free` | allocator exports |

### Keyboard

The host passes `pygame.event.key` plus `event.unicode` (so shifted
letters/symbols arrive already shifted).  The glue maps:
- printable ASCII (32..126) -> `AKEY_*` via an ASCII table (letters, digits,
  and all common punctuation/symbols),
- special keys (Return, Backspace, Escape, Tab, arrows, Delete, Insert) via a
  pygame-key table,
- emulator keys: F1=coldstart, F2=warmstart, F4=menu(no-op), F5=Start,
  F6=Select, F7=Option, F8=Break.

START/SELECT/OPTION are routed through `INPUT_key_consol` (GTIA CONSOL);
the rest go through `INPUT_key_code`.  `Atari800_Frame()` consumes
coldstart/warmstart/break in its `switch (INPUT_key_code)`.

### Framebuffer

`Screen_atari` is 384x240; the visible Atari screen is the middle 336 columns
(`Screen_visible_x1 = 24`, i.e. `ATARI_LEFT_MARGIN`).  Each byte is an Atari
color index; `Colours_table[idx]` holds packed `0x00RRGGBB`.  `wasi_tick()`
converts the visible 336x240 region to `g_fb[]` as 32-bit RGBA
(memory byte order R,G,B,A).

## Build

```bash
cd bin/3rdparty/atari800-wasi
bash -l -c 'source ~/emsdk/emsdk_env.sh && make'      # -> atari800.wasm
```

## Run

```bash
PYTHON=/home/jjs/Projects/atari800/yahtzee-a8/venv/hosts/venv-flat-line/bin/python
$PYTHON atari800_host.py                # interactive pygame window (PAL, scale 2)
$PYTHON atari800_host.py --ntsc         # NTSC @ 60 Hz
```

Headless validation (no window):

```bash
$PYTHON atari800_host.py --headless --pre-frames 150 --post-frames 30 \
    --type '10 PRINT "HELLO ATARI"' --preview
```

## Checklist

- [x] Create `bin/3rdparty/atari800-wasi/` directory
- [x] Write `config.h` (WASI) - no SDL/sound/signal/zlib
- [x] Write `cfg.h` / `cfg.c` - ROM path globals + no-op config
- [x] Write `ui.h` / `ui.c` - minimal UI stubs
- [x] Write `atari800-wasi.c` - glue, PLATFORM_*, framebuffer, keyboard
- [x] Write `Makefile` - emcc STANDALONE_WASM build
- [x] Build `atari800.wasm`
- [x] Write `atari800_host.py` - wasmtime binding + pygame renderer
- [x] Test: boot to Atari BASIC `READY.` with ATARIXL.ROM + ATARIBAS.ROM
- [x] Test: keyboard typing works (e.g. `PRINT 3+4` -> ` 7`)
- [ ] Integrate with root `Makefile` (`atari800` target -> `../wasi`)

## Future (Phase 2)

- POKEY audio buffer + `wasi_beep_pending` / `wasi_audio_ptr` exports
- `.atr` disk images via the preopened dir (`wasi_insert_disk`)
- Snapshot save/load
- ATARIOSB (OS-B) and 5200 support
- Joystick / paddles exports
