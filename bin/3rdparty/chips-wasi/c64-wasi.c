/*
 * c64-wasi.c — C64 WASI emulator module (headless, pure WASI)
 *
 * Renders into a raw 392×272 RGBA32 framebuffer in linear WASM memory.
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
 *   int    wasi_fb_width(void)                  - 392
 *   int    wasi_fb_height(void)                 - 272
 *   int    wasi_insert_disk(const uint8_t*,int,int) - stub, returns 0
 */

#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#define CHIPS_IMPL
#include "../chips/chips/chips_common.h"
#include "../chips/chips/m6502.h"
#include "../chips/chips/m6526.h"
#include "../chips/chips/m6522.h"
#include "../chips/chips/m6569.h"
#include "../chips/chips/m6581.h"
#include "../chips/chips/kbd.h"
#include "../chips/chips/mem.h"
#include "../chips/chips/clk.h"
#include "../chips/systems/c1530.h"
#include "../chips/systems/c1541.h"
#include "../chips/systems/c64.h"

#include "c64_roms.h"

/* ── Emulator state ─────────────────────────────────────────────────── */

static c64_t g_sys;

/* ── RGBA32 framebuffer: visible 392×272 region from the raw 504×312 fb ── */
#define VISIBLE_W 392
#define VISIBLE_H 272
#define VISIBLE_X 64
#define VISIBLE_Y 24

static uint32_t g_fb[VISIBLE_W * VISIBLE_H];

/* ── Exported: init ─────────────────────────────────────────────────── */

void wasi_init(void) {
    c64_init(&g_sys, &(c64_desc_t){
        .c1530_enabled  = false,
        .c1541_enabled  = false,
        .joystick_type  = C64_JOYSTICKTYPE_NONE,
        .roms = {
            .chars  = { .ptr = g_rom_c64_char,  .size = 4096 },
            .basic  = { .ptr = g_rom_c64_basic, .size = 8192 },
            .kernal = { .ptr = g_rom_c64_kernal,.size = 8192 },
            .c1541 = { {0}, {0} },
        },
        .audio = { .callback = { 0 } },
    });
    memset(g_fb, 0, sizeof(g_fb));
}

/* ── Exported: tick ─────────────────────────────────────────────────── */

void wasi_tick(void) {
    /* ~1/60 s = 1,000,000 / 60 ≈ 16,665 µs   (C64 clock: 985,248 Hz) */
    c64_exec(&g_sys, 16665);

    /* Convert visible 392×272 region from indexed (0-15) to RGBA32.
     * The raw framebuffer is 504×312 indexed bytes; we extract the
     * visible rectangle (x=64, y=24, w=392, h=272) and palette-lookup
     * each pixel via m6569_color(). */
    int raw_w = M6569_FRAMEBUFFER_WIDTH;  /* 504 */

    for (int y = 0; y < VISIBLE_H; y++) {
        for (int x = 0; x < VISIBLE_W; x++) {
            int raw_y = y + VISIBLE_Y;
            int raw_x = x + VISIBLE_X;
            uint8_t idx = g_sys.fb[raw_y * raw_w + raw_x];
            g_fb[y * VISIBLE_W + x] = m6569_color(idx & 0x0F);
        }
    }
}

/* ── Exported: input ────────────────────────────────────────────────── */

int wasi_keydown(int code) {
    c64_key_down(&g_sys, code);
    return 1;
}

int wasi_keyup(int code) {
    c64_key_up(&g_sys, code);
    return 1;
}

/* ── Exported: framebuffer access ───────────────────────────────────── */

int wasi_fb_ptr(void)    { return (int)(size_t)g_fb; }
int wasi_fb_width(void)  { return VISIBLE_W; }
int wasi_fb_height(void) { return VISIBLE_H; }

/* ── Exported: debug — read C64 text screen RAM ($0400, 40x25) ─────── */

int wasi_screen_cols(void) { return 40; }
int wasi_screen_rows(void) { return 25; }

void wasi_screen_text(uint8_t *out, int max_len) {
    int n = 40 * 25;
    if (max_len < n) { n = max_len; }
    for (int i = 0; i < n; i++) {
        out[i] = mem_rd(&g_sys.mem_cpu, 0x0400 + i);
    }
}

/* ── Exported: disk (stub for Phase 2) ──────────────────────────────── */

int wasi_insert_disk(const uint8_t *data, int size, int drive) {
    (void)data; (void)size; (void)drive;
    return 0;
}

/* ── main() — never called directly; Python host calls wasi_init()+tick() ── */

int main(void) {
    wasi_init();
    return 0;
}