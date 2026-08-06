/*
 * atari800-wasi.c - Atari800 (2.2.1 core) as a pure-WASI wasmtime module.
 *
 * Renders the visible Atari screen (336x240) into a linear RGBA framebuffer
 * that a Python host reads via wasmtime and displays with pygame.  No SDL2,
 * no browser deps.  Follows the chips-wasi / reinette-II-plus pattern.
 *
 * Build:
 *   bash -l -c 'source ~/emsdk/emsdk_env.sh && make'     # -> atari800.wasm
 *
 * Run (from Python via wasmtime):
 *   import wasmtime
 *   engine  = wasmtime.Engine()
 *   module  = wasmtime.Module.from_file(engine, "atari800.wasm")
 *   linker  = wasmtime.Linker(engine)
 *   linker.define_wasi()
 *   store   = wasmtime.Store(engine)
 *   wasi    = wasmtime.WasiConfig(); wasi.preopen_dir("/roms", "Distribution/Rom")
 *   store.set_wasi(wasi)
 *   inst    = linker.instantiate(store, module)
 *
 *   # IMPORTANT: do NOT call the exported "_start".  Call wasi_init() once,
 *   # then wasi_tick() at ~50/60 Hz.  Read the framebuffer via wasi_fb_ptr().
 *
 * Exported API:
 *   void wasi_init(void)                    - load ROMs (from /roms), init, coldstart
 *   void wasi_tick(void)                    - run one Atari frame, render framebuffer
 *   int  wasi_keydown(int pg_key, int unicode)  - inject key press
 *   int  wasi_keyup(int pg_key, int unicode)    - inject key release
 *   int  wasi_fb_ptr(void)                  - address of g_fb in linear memory
 *   int  wasi_fb_width(void)                - 336
 *   int  wasi_fb_height(void)               - 240
 *   int  wasi_fb_raw_ptr(void)              - address of Screen_atari (384x240)
 *   int  wasi_fb_raw_width(void)            - 384
 *   int  wasi_fb_raw_height(void)           - 240
 *   int  wasi_screen_cols(void)             - 40 (text screen width)
 *   int  wasi_screen_rows(void)             - 24 (text screen height)
 *   int  wasi_screen_text(UBYTE*, int)      - copy text screen (internal codes)
 *   int  wasi_insert_disk(const uint8_t*, int, int)  - stub
 */

#include "config.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "akey.h"
#include "atari.h"
#include "cfg.h"
#include "colours.h"
#include "input.h"
#include "log.h"
#include "memory.h"
#include "platform.h"
#include "screen.h"
#include "util.h"

/* ============================ Framebuffer ============================ */

#define FB_W 336
#define FB_H 240

static uint32_t g_fb[FB_W * FB_H];

/* Convert the visible part of Screen_atari (384x240, one color-index byte
   per pixel, visible 336x240 starting at column 24) into an RGBA32 buffer.
   Colours_table[idx] holds packed 0x00RRGGBB; we emit memory byte order
   R,G,B,A. */
static void render_fb(void)
{
    const int RAW_W = Screen_WIDTH;   /* 384 */
    const int LEFT = 24;              /* ATARI_LEFT_MARGIN / Screen_visible_x1 */
    const UBYTE *src = (const UBYTE *) Screen_atari;
    int y;
    for (y = 0; y < FB_H; y++) {
        const UBYTE *row = src + y * RAW_W + LEFT;
        uint32_t *dst = g_fb + y * FB_W;
        int x;
        for (x = 0; x < FB_W; x++) {
            UBYTE idx = row[x];
            dst[x] = 0xFF000000u
                | ((uint32_t) Colours_GetR(idx))
                | ((uint32_t) Colours_GetG(idx) << 8)
                | ((uint32_t) Colours_GetB(idx) << 16);
        }
    }
}

/* ============================== Keyboard ============================== */

/* pygame event.key constants (SDL1/pygame style) passed by the host. */
#define K_RETURN    13
#define K_BACKSPACE 8
#define K_ESCAPE    27
#define K_TAB       9
#define K_UP        273
#define K_DOWN      274
#define K_RIGHT     275
#define K_LEFT      276
#define K_DELETE    127
#define K_INSERT    277
#define K_F1        282
#define K_F2        283
#define K_F4        285
#define K_F5        286
#define K_F6        287
#define K_F7        288
#define K_F8        289

/* Map a printable ASCII character to an Atari AKEY_* value. */
static int ascii_to_akey(int c)
{
    switch (c) {
    case ' ':  return AKEY_SPACE;
    case 'a':  return AKEY_a;   case 'b': return AKEY_b;   case 'c': return AKEY_c;
    case 'd':  return AKEY_d;   case 'e': return AKEY_e;   case 'f': return AKEY_f;
    case 'g':  return AKEY_g;   case 'h': return AKEY_h;   case 'i': return AKEY_i;
    case 'j':  return AKEY_j;   case 'k': return AKEY_k;   case 'l': return AKEY_l;
    case 'm':  return AKEY_m;   case 'n': return AKEY_n;   case 'o': return AKEY_o;
    case 'p':  return AKEY_p;   case 'q': return AKEY_q;   case 'r': return AKEY_r;
    case 's':  return AKEY_s;   case 't': return AKEY_t;   case 'u': return AKEY_u;
    case 'v':  return AKEY_v;   case 'w': return AKEY_w;   case 'x': return AKEY_x;
    case 'y':  return AKEY_y;   case 'z': return AKEY_z;
    case 'A':  return AKEY_A;   case 'B': return AKEY_B;   case 'C': return AKEY_C;
    case 'D':  return AKEY_D;   case 'E': return AKEY_E;   case 'F': return AKEY_F;
    case 'G':  return AKEY_G;   case 'H': return AKEY_H;   case 'I': return AKEY_I;
    case 'J':  return AKEY_J;   case 'K': return AKEY_K;   case 'L': return AKEY_L;
    case 'M':  return AKEY_M;   case 'N': return AKEY_N;   case 'O': return AKEY_O;
    case 'P':  return AKEY_P;   case 'Q': return AKEY_Q;   case 'R': return AKEY_R;
    case 'S':  return AKEY_S;   case 'T': return AKEY_T;   case 'U': return AKEY_U;
    case 'V':  return AKEY_V;   case 'W': return AKEY_W;   case 'X': return AKEY_X;
    case 'Y':  return AKEY_Y;   case 'Z': return AKEY_Z;
    case '0':  return AKEY_0;   case '1': return AKEY_1;   case '2': return AKEY_2;
    case '3':  return AKEY_3;   case '4': return AKEY_4;   case '5': return AKEY_5;
    case '6':  return AKEY_6;   case '7': return AKEY_7;   case '8': return AKEY_8;
    case '9':  return AKEY_9;
    case '!':  return AKEY_EXCLAMATION;
    case '"':  return AKEY_DBLQUOTE;
    case '#':  return AKEY_HASH;
    case '$':  return AKEY_DOLLAR;
    case '%':  return AKEY_PERCENT;
    case '&':  return AKEY_AMPERSAND;
    case '\'': return AKEY_QUOTE;
    case '(':  return AKEY_PARENLEFT;
    case ')':  return AKEY_PARENRIGHT;
    case '*':  return AKEY_ASTERISK;
    case '+':  return AKEY_PLUS;
    case ',':  return AKEY_COMMA;
    case '-':  return AKEY_MINUS;
    case '.':  return AKEY_FULLSTOP;
    case '/':  return AKEY_SLASH;
    case ':':  return AKEY_COLON;
    case ';':  return AKEY_SEMICOLON;
    case '<':  return AKEY_LESS;
    case '=':  return AKEY_EQUAL;
    case '>':  return AKEY_GREATER;
    case '?':  return AKEY_QUESTION;
    case '@':  return AKEY_AT;
    case '[':  return AKEY_BRACKETLEFT;
    case '\\': return AKEY_BACKSLASH;
    case ']':  return AKEY_BRACKETRIGHT;
    case '^':  return AKEY_CIRCUMFLEX;
    case '_':  return AKEY_UNDERSCORE;
    default:   return AKEY_NONE;
    }
}

/* Map pygame special/emulator keys to AKEY_* values. */
static int pygame_to_akey(int pg_key)
{
    switch (pg_key) {
    case K_RETURN:    return AKEY_RETURN;
    case K_BACKSPACE: return AKEY_BACKSPACE;
    case K_ESCAPE:    return AKEY_ESCAPE;
    case K_TAB:       return AKEY_TAB;
    case K_UP:        return AKEY_UP;
    case K_DOWN:      return AKEY_DOWN;
    case K_LEFT:      return AKEY_LEFT;
    case K_RIGHT:     return AKEY_RIGHT;
    case K_DELETE:    return AKEY_DELETE_CHAR;
    case K_INSERT:    return AKEY_INSERT_CHAR;
    case K_F1:        return AKEY_COLDSTART;  /* reboot */
    case K_F2:        return AKEY_WARMSTART;  /* reset */
    case K_F4:        return AKEY_UI;         /* menu (no-op) */
    case K_F5:        return AKEY_START;      /* console Start */
    case K_F6:        return AKEY_SELECT;     /* console Select */
    case K_F7:        return AKEY_OPTION;     /* console Option */
    case K_F8:        return AKEY_BREAK;
    default:          return AKEY_NONE;
    }
}

/* Unicode (printable) takes priority; otherwise use the pygame keycode. */
static int resolve_key(int pg_key, int unicode_char)
{
    int code = AKEY_NONE;
    if (unicode_char >= 32 && unicode_char <= 126)
        code = ascii_to_akey(unicode_char);
    if (code == AKEY_NONE)
        code = pygame_to_akey(pg_key);
    return code;
}

/* Apply a press (is_down=1) or release (is_down=0) for an AKEY code.
   Console keys go through INPUT_key_consol (GTIA CONSOL switches); the
   rest go through INPUT_key_code. */
static void key_action(int code, int is_down)
{
    switch (code) {
    case AKEY_START:
        if (is_down) INPUT_key_consol &= ~INPUT_CONSOL_START;
        else         INPUT_key_consol |= INPUT_CONSOL_START;
        break;
    case AKEY_SELECT:
        if (is_down) INPUT_key_consol &= ~INPUT_CONSOL_SELECT;
        else         INPUT_key_consol |= INPUT_CONSOL_SELECT;
        break;
    case AKEY_OPTION:
        if (is_down) INPUT_key_consol &= ~INPUT_CONSOL_OPTION;
        else         INPUT_key_consol |= INPUT_CONSOL_OPTION;
        break;
    default:
        INPUT_key_code = is_down ? code : AKEY_NONE;
        break;
    }
}

/* ============================ Platform glue ============================ */

int PLATFORM_Initialise(int *argc, char *argv[])
{
    (void) argc;
    (void) argv;
    return TRUE;
}

int PLATFORM_Exit(int run_monitor)
{
    (void) run_monitor;
    return FALSE; /* no restart */
}

int PLATFORM_Keyboard(void)
{
    return 0;
}

void PLATFORM_DisplayScreen(void)
{
    /* The host renders the framebuffer after wasi_tick(). */
}

int PLATFORM_PORT(int num)
{
    (void) num;
    /* Two joysticks per call (nibbles 0-3 and 4-7), all centred.
       INPUT_STICK_CENTRE = 0x0f. */
    return 0x0f | (0x0f << 4);
}

int PLATFORM_TRIG(int num)
{
    (void) num;
    return 1; /* trigger not pressed */
}

void PLATFORM_Sleep(double s)
{
    (void) s; /* the Python host paces the frame rate */
}

/* ============================= WASI exports ============================= */

void wasi_init(void)
{
    int argc = 1;
    char *argv[2] = { (char *) "atari800-wasi", NULL };

    /* ROM images are embedded in the module (gen_roms.py -> atari800_roms.h)
       and served by Atari800_LoadImage() under WASI_EMBED_ROMS.  The paths
       here only need to match the embedded-ROM lookup (strstr). */
    Util_strlcpy(CFG_xlxe_filename, "/roms/ATARIXL.ROM", sizeof(CFG_xlxe_filename));
    Util_strlcpy(CFG_basic_filename, "/roms/ATARIBAS.ROM", sizeof(CFG_basic_filename));

    INPUT_key_code = AKEY_NONE;
    INPUT_key_consol = INPUT_CONSOL_NONE;

    if (!Atari800_Initialise(&argc, argv)) {
        Log_print("atari800-wasi: Atari800_Initialise failed");
        return;
    }
    Atari800_Coldstart();
}

void wasi_tick(void)
{
    Atari800_Frame();
    if (Atari800_display_screen)
        render_fb();
}

int wasi_keydown(int pg_key, int unicode_char)
{
    int code = resolve_key(pg_key, unicode_char);
    if (code == AKEY_NONE)
        return 0;
    key_action(code, 1);
    return 1;
}

int wasi_keyup(int pg_key, int unicode_char)
{
    int code = resolve_key(pg_key, unicode_char);
    if (code == AKEY_NONE) {
        INPUT_key_code = AKEY_NONE;
        return 0;
    }
    key_action(code, 0);
    return 1;
}

int wasi_fb_ptr(void)        { return (int) (uintptr_t) g_fb; }
int wasi_fb_width(void)      { return FB_W; }
int wasi_fb_height(void)     { return FB_H; }
int wasi_fb_raw_ptr(void)    { return (int) (uintptr_t) Screen_atari; }
int wasi_fb_raw_width(void)  { return Screen_WIDTH; }
int wasi_fb_raw_height(void) { return Screen_HEIGHT; }

int wasi_screen_cols(void)   { return 40; }
int wasi_screen_rows(void)   { return 24; }

/* Copy the text screen (internal codes) into buf.  The screen base comes
   from the OS SAVMSC pointer ($0058/$0059); for a standard 40x24 text
   screen this is the 40x24 editor window.  Returns bytes copied (0). */
int wasi_screen_text(UBYTE *buf, int n)
{
    const int bytes = 40 * 24;
    int base = MEMORY_mem[0x58] | (MEMORY_mem[0x59] << 8); /* SAVMSC */
    int i;
    if (n < bytes)
        return 0;
    if (base < 0x4000 || base > 0xBF00)
        base = 0xBC40; /* fallback: standard XL/XE 40x24 screen */
    for (i = 0; i < bytes; i++)
        buf[i] = MEMORY_mem[base + i];
    return bytes;
}

/* Stub - future .atr disk image insertion. */
int wasi_insert_disk(const uint8_t *data, int size, int drive)
{
    (void) data;
    (void) size;
    (void) drive;
    return 0;
}

/* Standard entry point: initialises the module if the host calls _start
   (the wasmtime host normally calls wasi_init() directly instead). */
int main(void)
{
    wasi_init();
    return 0;
}
