/*
 * vic20-wasi.c — VIC-20 WASI emulator module (headless, pure WASI)
 *
 * Renders into a raw 232×272 RGBA32 framebuffer in linear WASM memory.
 * The Python host reads the framebuffer via wasmtime and displays with pygame.
 *
 * No audio, no floppy, no tape — boots to BASIC READY.
 *
 * Exported API:
 *   void   wasi_init(void)                      - load ROMs, reset CPU
 *   void   wasi_tick(void)                      - run one emulator frame (~60 Hz)
 *   int    wasi_keydown(int code)               - inject key press
 *   int    wasi_keyup(int code)                 - inject key release
 *   int    wasi_fb_ptr(void)                    - address of g_fb in linear mem
 *   int    wasi_fb_width(void)                  - 232
 *   int    wasi_fb_height(void)                 - 272
 *   int    wasi_insert_disk(const uint8_t*,int,int) - stub, returns 0
 */

#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#define CHIPS_IMPL
#include "../chips/chips/chips_common.h"
#include "../chips/chips/m6502.h"
#include "../chips/chips/m6522.h"
#include "../chips/chips/m6561.h"
#include "../chips/chips/kbd.h"
#include "../chips/chips/mem.h"
#include "../chips/chips/clk.h"
#include "../chips/systems/c1530.h"
#include "../chips/systems/vic20.h"

#include "vic20_roms.h"

/* ── Emulator state ─────────────────────────────────────────────────── */

static vic20_t g_sys;

/* ── RGBA32 framebuffer: visible 232×272 region from the raw 512×320 fb.
 * The chips m6561 writes the visible screen content at the TOP-LEFT of the
 * raw framebuffer (origin 0,0), so VISIBLE_X/Y are 0 — the _VIC20_SCREEN_X/Y
 * constants are the m6561 internal vis_x0 in ticks, NOT framebuffer offsets. */
#define VISIBLE_W 232
#define VISIBLE_H 272
#define VISIBLE_X 0
#define VISIBLE_Y 0

static uint32_t g_fb[VISIBLE_W * VISIBLE_H];

/* ── Exported: init ─────────────────────────────────────────────────── */

void wasi_init(void) {
    vic20_init(&g_sys, &(vic20_desc_t){
        .c1530_enabled  = false,
        .joystick_type  = VIC20_JOYSTICKTYPE_NONE,
        .mem_config     = VIC20_MEMCONFIG_STANDARD,
        .roms = {
            .chars  = { .ptr = g_rom_vic20_char,  .size = 4096 },
            .basic  = { .ptr = g_rom_vic20_basic, .size = 8192 },
            .kernal = { .ptr = g_rom_vic20_kernal,.size = 8192 },
        },
        .audio = { .callback = { 0 } },
    });
    /* chips' vic20 keymap registers the Ctrl MODIFIER (layer 1, col 2, line 0)
     * but no key code for the Ctrl key itself, so vic20_key_down(0x0E) would
     * be a no-op.  Register the Ctrl key at the modifier's matrix position so
     * the host can send CBM_KEY_CTRL (0x0E) to activate Ctrl, which makes
     * Ctrl+letter produce graphics characters. */
    kbd_register_key(&g_sys.kbd, 0x0E, 2, 0, 0);
    memset(g_fb, 0, sizeof(g_fb));
}

/* ── Exported: tick ─────────────────────────────────────────────────── */

void wasi_tick(void) {
    /* ~1/60 s = 1,000,000 / 60 ≈ 16,666 µs   (VIC-20 clock: 1,108,404 Hz) */
    vic20_exec(&g_sys, 16666);

    /* Convert visible 232×272 region from indexed (0-15) to RGBA32.
     * The raw framebuffer is 512×320 indexed bytes; we extract the
     * visible rectangle (x=32, y=8, w=232, h=272) and palette-lookup
     * each pixel via m6561_color(). */
    int raw_w = M6561_FRAMEBUFFER_WIDTH;  /* 512 */

    for (int y = 0; y < VISIBLE_H; y++) {
        for (int x = 0; x < VISIBLE_W; x++) {
            int raw_y = y + VISIBLE_Y;
            int raw_x = x + VISIBLE_X;
            uint8_t idx = g_sys.fb[raw_y * raw_w + raw_x];
            g_fb[y * VISIBLE_W + x] = m6561_color(idx & 0x0F);
        }
    }
}

/* ── Exported: input ────────────────────────────────────────────────── */

int wasi_keydown(int code) {
    vic20_key_down(&g_sys, code);
    return 1;
}

int wasi_keyup(int code) {
    vic20_key_up(&g_sys, code);
    return 1;
}

/* ── Exported: framebuffer access ───────────────────────────────────── */

int wasi_fb_ptr(void)    { return (int)(size_t)g_fb; }
int wasi_fb_width(void)  { return VISIBLE_W; }
int wasi_fb_height(void) { return VISIBLE_H; }

/* ── Exported: debug — access to the raw indexed VIC framebuffer ───── */

int  wasi_fb_raw_width(void)  { return M6561_FRAMEBUFFER_WIDTH; }   /* 512 */
int  wasi_fb_raw_height(void) { return M6561_FRAMEBUFFER_HEIGHT; }  /* 320 */
int  wasi_fb_raw_ptr(void)    { return (int)(size_t)g_sys.fb; }

/* ── Exported: debug — read VIC-20 text screen RAM ($1E00, 22x23) ──── */

int wasi_screen_cols(void) { return 22; }
int wasi_screen_rows(void) { return 23; }

void wasi_screen_text(uint8_t *out, int max_len) {
    int n = 22 * 23;
    if (max_len < n) { n = max_len; }
    for (int i = 0; i < n; i++) {
        out[i] = mem_rd(&g_sys.mem_cpu, 0x1E00 + i);
    }
}

/* ── Exported: disk (stub for Phase 2) ──────────────────────────────── */

int wasi_insert_disk(const uint8_t *data, int size, int drive) {
    (void)data; (void)size; (void)drive;
    return 0;
}

/* ── Exported: auto-load a PRG file directly into RAM ───────────────── */
/* The PRG format is:
 *   uint16_t load_addr (little-endian)
 *   uint8_t  data[load_size]
 *
 * vic20_quickload() copies the payload into memory at load_addr but, unlike
 * c64_quickload(), it does NOT update the BASIC variable-table pointers.
 * We replicate the pointer updates c64_quickload() performs so that typing
 * RUN finds a valid program: $2D/$2F/$31/$33/$AE are set to the end of the
 * loaded program.  (VIC-20 uses the same Commodore BASIC V2 zero-page
 * layout as the C64.)
 */

int wasi_load_prg(const uint8_t *prg_data, int prg_size) {
    if (!prg_data || prg_size < 2) {
        return -1;  /* invalid input */
    }
    uint16_t addr = (uint16_t)((unsigned)prg_data[0] | ((unsigned)prg_data[1] << 8));
    int payload_len = prg_size - 2;

    /* Safety: don't write past the end of the 64 KB address space. */
    if ((addr + payload_len) > 0x10000) {
        return -2;
    }

    chips_range_t range = { (void*)prg_data, (size_t)prg_size };
    if (!vic20_quickload(&g_sys, range)) {
        return -3;
    }

    /* Update the BASIC variable-table pointers (mirrors c64_quickload). */
    uint16_t end_addr = addr + payload_len;
    mem_wr16(&g_sys.mem_cpu, 0x2d, end_addr);
    mem_wr16(&g_sys.mem_cpu, 0x2f, end_addr);
    mem_wr16(&g_sys.mem_cpu, 0x31, end_addr);
    mem_wr16(&g_sys.mem_cpu, 0x33, end_addr);
    mem_wr16(&g_sys.mem_cpu, 0xae, end_addr);

    return 0;
}

/* ── main() — never called directly; Python host calls wasi_init()+tick() ── */

int main(void) {
    wasi_init();
    return 0;
}