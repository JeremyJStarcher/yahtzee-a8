# chips-wasi: VIC-20 and C64 WASI Emulators (Milestone 1 — Boot to BASIC)

## Goal

Two standalone `.wasm` modules (`vic20.wasm`, `c64.wasm`) that boot a VIC-20 or C64
to the Commodore BASIC READY prompt. Driven by Python hosts using pygame via
`wasmtime-py`. No disk, no tape, no audio.

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

Source: `/home/jjs/Projects/myemu/vice-roms`

| Machine | File | Role | Size |
|---------|------|------|------|
| VIC-20 | `VIC20/chargen-901460-03.bin` | Character ROM | 4096 B |
| VIC-20 | `VIC20/basic-901486-01.bin` | BASIC ROM | 8192 B |
| VIC-20 | `VIC20/kernal.901486-07.bin` | KERNAL ROM | 8192 B |
| C64 | `C64/chargen-901225-01.bin` | Character ROM | 4096 B |
| C64 | `C64/basic-901226-01.bin` | BASIC ROM | 8192 B |
| C64 | `C64/kernal-901227-03.bin` | KERNAL ROM | 8192 B |

## Directory: `bin/3rdparty/chips-wasi/`

```
chips-wasi/
├── PLAN.md                ← this file
├── gen_roms.py            # ROM binary → C header (xxd -i style)
├── keymaps.h              # pygame event.key → Commodore key codes
├── vic20-wasi.c           # WASI glue for VIC-20
├── c64-wasi.c             # WASI glue for C64
├── Makefile               # emcc build rules for vic20.wasm, c64.wasm
├── vic20_host.py          # Python host: VIC-20
└── c64_host.py            # Python host: C64
```

Generated (by `gen_roms.py`):
```
├── vic20_roms.h           # uint8_t g_rom_vic20_char[4096], etc.
└── c64_roms.h             # uint8_t g_rom_c64_char[4096], etc.
```

Built (by `Makefile`):
```
├── vic20.wasm
└── c64.wasm
```

## File-by-File Spec

### 1. `gen_roms.py`

Reads each binary ROM file, writes a C header with `static const uint8_t` arrays.
Same style as `wasi_roms.h` in reinette-II-plus.

```python
def rom_to_header(bin_path, array_name, out_fh):
    data = Path(bin_path).read_bytes()
    out_fh.write(f"static const uint8_t {array_name}[{len(data)}] = {{\n")
    for i in range(0, len(data), 16):
        out_fh.write("    " + ",".join(f"0x{b:02X}" for b in data[i:i+16]) + ",\n")
    out_fh.write("};\n")
```

### 2. `keymaps.h`

Each entry: `{ pygame_keycode, commodore_key_code }`. Shared by both hosts.

The Commodore key codes matches those registered in `_vic20_init_key_map()` /
`_c64_init_key_map()` — mostly ASCII for printable characters, special codes
for function keys, cursor keys, etc.

Special codes (both machines):
- `0x01` — DEL
- `0x03` — RUN/STOP
- `0x08` — cursor left (shift+crsr right)
- `0x09` — cursor right
- `0x0A` — cursor down
- `0x0B` — cursor up
- `0x0D` — RETURN
- `0x0E` — CTRL
- `0x0F` — C= (C64 only)
- `0x0C` — HOME (C64 only)
- `0x02` — CLR (C64 only)
- `0x04` — LEFT ARROW (C64 only)
- `0x10` — INST (C64 only)
- `0xFF` — RESTORE
- `0xF1`–`0xF8` — F1–F8

### 3. `vic20-wasi.c`

**Exported API** (same as reinette-wasi.c):
- `void wasi_init(void)` — ROMs → vic20_init(), reset CPU
- `void wasi_tick(void)` — vic20_exec(16666), palette-convert fb to RGBA32
- `int wasi_keydown(int code)` → `vic20_key_down()`
- `int wasi_keyup(int code)` → `vic20_key_up()`
- `int wasi_fb_ptr(void)` — address of g_fb
- `int wasi_fb_width(void)` — 232
- `int wasi_fb_height(void)` — 272
- `int wasi_insert_disk(const uint8_t*, int, int)` — **stub, returns 0** (future Phase 2)

**No audio exports** (no `wasi_beep_pending`, no `wasi_ack_beep`).

**Internals**:
```c
#define CHIPS_IMPL
#include "chips/chips_common.h"
#include "chips/m6502.h"
#include "chips/m6522.h"
#include "chips/m6561.h"
#include "chips/kbd.h"
#include "chips/mem.h"
#include "chips/clk.h"
#include "systems/c1530.h"
#include "systems/vic20.h"
#include "vic20_roms.h"

static vic20_t g_sys;
static uint32_t g_fb[232 * 272];  // RGBA32

void wasi_init(void) {
    vic20_init(&g_sys, &(vic20_desc_t){
        .c1530_enabled = false,
        .joystick_type = VIC20_JOYSTICKTYPE_NONE,
        .mem_config = VIC20_MEMCONFIG_STANDARD,
        .roms = {
            .chars  = { .ptr = g_rom_vic20_char,  .size = 4096 },
            .basic  = { .ptr = g_rom_vic20_basic, .size = 8192 },
            .kernal = { .ptr = g_rom_vic20_kernal,.size = 8192 },
        },
        .audio = { .callback = { 0 } },
    });
}

void wasi_tick(void) {
    vic20_exec(&g_sys, 16666);  // ~60 Hz
    // convert visible 232x272 region from indexed to RGBA32
    int fw = M6561_FRAMEBUFFER_WIDTH;  // 512
    int vx = 32, vy = 8, vw = 232, vh = 272;
    for (int y = 0; y < vh; y++) {
        for (int x = 0; x < vw; x++) {
            uint8_t idx = g_sys.fb[(y + vy) * fw + (x + vx)];
            g_fb[y * vw + x] = m6561_color(idx & 0x0F);
        }
    }
}
```

**Build flags**:
```makefile
CFLAGS = -std=c11 -Wall -I../chips
WASI_FLAGS = -sSTANDALONE_WASM=1 -sINITIAL_MEMORY=67108864 -O3
EXPORTS = _wasi_init, _wasi_tick, _wasi_keydown, _wasi_keyup, \
          _wasi_fb_ptr, _wasi_fb_width, _wasi_fb_height, \
          _wasi_insert_disk, _malloc, _free
```

### 4. `c64-wasi.c`

Same pattern but:
- Includes chain: `chips_common.h`, `m6502.h`, `m6526.h`, `m6569.h`, `m6581.h`, `kbd.h`, `mem.h`, `clk.h`, `c1530.h`, `c1541.h`, `m6522.h`, `systems/c64.h`
- FB dimensions: visible 392×272 (from raw 63×8=504 by 312)
  - `_C64_SCREEN_WIDTH` = 392, `_C64_SCREEN_HEIGHT` = 272
  - `_C64_SCREEN_X` = 64, `_C64_SCREEN_Y` = 24
  - raw fb width = `M6569_FRAMEBUFFER_WIDTH` = 63 * 8 = 504
- `c64_exec(&g_sys, 16665)` (~60 Hz at 985248 Hz)
- No SID audio callback (`.audio.callback = {0}`)
- No C1541 (`.c1541_enabled = false`)

### 5. `vic20_host.py` / `c64_host.py`

Clean pygame host — no terminal fallback.

```python
#!/usr/bin/env python3
import sys
from pathlib import Path
# venv bootstrap
_VENV = Path("/home/jjs/Projects/atari800/yahtzee-a8/venv/hosts/venv-flat-line/lib/python3.12/site-packages")
if str(_VENV) not in sys.path: sys.path.insert(0, str(_VENV))

import wasmtime, pygame, argparse

class Emulator:
    def __init__(self, wasm_path, fb_w, fb_h):
        self.FB_W = fb_w
        self.FB_H = fb_h
        engine = wasmtime.Engine()
        self.store = wasmtime.Store(engine)
        self.store.set_wasi(wasmtime.WasiConfig())
        linker = wasmtime.Linker(engine)
        linker.define_wasi()
        module = wasmtime.Module.from_file(engine, wasm_path)
        inst = linker.instantiate(self.store, module)
        e = inst.exports(self.store)
        self._mem = e["memory"]
        self._init = e["wasi_init"]
        self._tick = e["wasi_tick"]
        self._kd = e["wasi_keydown"]
        self._ku = e["wasi_keyup"]
        self._fb = e["wasi_fb_ptr"]

    def init(self):  self._init(self.store)
    def tick(self):  self._tick(self.store)
    def keydown(self, c): self._kd(self.store, c)
    def keyup(self, c):   self._ku(self.store, c)
    def framebuffer(self):
        ptr = self._fb(self.store)
        n = self.FB_W * self.FB_H * 4
        return self._mem.read(self.store, ptr, ptr + n)

def pygame_key_to_commodore(pg_key):
    """Map pygame key constant → Commodore key code."""
    # ... lookup table from keymaps.h equivalent ...
    table = {
        pygame.K_a: 0x41, pygame.K_b: 0x42, ...  # 'A', 'B' etc
        pygame.K_SPACE: 0x20,
        pygame.K_RETURN: 0x0D,
        pygame.K_BACKSPACE: 0x08,  # cursor left
        pygame.K_DELETE: 0x01,     # DEL
        pygame.K_F1: 0xF1,
        ...
    }
    return table.get(pg_key, -1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--wasm", required=True)
    ap.add_argument("--fbw", type=int, required=True)
    ap.add_argument("--fbh", type=int, required=True)
    args = ap.parse_args()

    pygame.init()
    emu = Emulator(args.wasm, args.fbw, args.fbh)
    emu.init()
    screen = pygame.display.set_mode((args.fbw * args.scale, args.fbh * args.scale))
    clock = pygame.time.Clock()
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: running = False
            elif ev.type == pygame.KEYDOWN:
                c = pygame_key_to_commodore(ev.key)
                if c >= 0: emu.keydown(c)
            elif ev.type == pygame.KEYUP:
                c = pygame_key_to_commodore(ev.key)
                if c >= 0: emu.keyup(c)
        emu.tick()
        fb = emu.framebuffer()
        surf = pygame.image.frombuffer(fb, (emu.FB_W, emu.FB_H), "RGBA")
        scaled = pygame.transform.scale(surf, (emu.FB_W * args.scale, emu.FB_H * args.scale))
        screen.blit(scaled, (0, 0))
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()

if __name__ == "__main__":
    main()
```

VIC-20 invocation:
```bash
python3 vic20_host.py --wasm vic20.wasm --fbw 232 --fbh 272 --scale 3
```
C64 invocation:
```bash
python3 c64_host.py --wasm c64.wasm --fbw 392 --fbh 272 --scale 2
```

Or bake FB dimensions into each host file (no `--fbw`/`--fbh` args needed).

## Build Steps

```bash
cd bin/3rdparty/chips-wasi
python3 gen_roms.py                          # → vic20_roms.h, c64_roms.h
source ~/emsdk/emsdk_env.sh
make vic20.wasm c64.wasm                     # compile WASM modules
```

## Test Steps

```bash
PYTHON=/home/jjs/Projects/atari800/yahtzee-a8/venv/hosts/venv-flat-line/bin/python
$PYTHON vic20_host.py --wasm vic20.wasm       # should show BASIC READY
$PYTHON c64_host.py  --wasm c64.wasm         # should show BASIC READY
```

## Checklist

- [ ] Create `bin/3rdparty/chips-wasi/` directory
- [ ] Write `gen_roms.py` and run it — verify `vic20_roms.h` and `c64_roms.h` exist
- [ ] Write `keymaps.h` — pygame → Commodore key code tables
- [ ] Write `vic20-wasi.c` — VIC-20 WASI glue
- [ ] Write `c64-wasi.c` — C64 WASI glue
- [ ] Write `Makefile` — emcc build rules
- [ ] Build `vic20.wasm`
- [ ] Build `c64.wasm`
- [ ] Write `vic20_host.py` — pygame host
- [ ] Write `c64_host.py` — pygame host
- [ ] Test VIC-20: verify BASIC READY prompt, keyboard input works
- [ ] Test C64: verify BASIC READY prompt, keyboard input works

## Future (Phase 2)

- SID audio / VIC audio
- C1541 floppy disk support (C64)
- Datassette tape support
- C1541 floppy support for VIC-20 (needs manual IEC bus wiring)
- `.d64` / `.tap` / `.prg` file handling via WASI preopened dirs
- Snapshot save/load