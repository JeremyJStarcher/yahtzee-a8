/*
 * Reinette II plus - WASI / wasmtime port (headless framebuffer)
 *
 * This is a pure-WASI build with NO SDL2 and NO browser dependencies.
 * It renders into a raw 280x192 RGBA framebuffer in linear memory that the
 * Python host reads via wasmtime and displays with pygame (or similar).
 *
 * Build:
 *   source ~/emsdk/emsdk_env.sh && make -f Makefile.wasi wasi
 *
 * Run (from Python via wasmtime):
 *   import wasmtime
 *   engine = wasmtime.Engine()
 *   module = wasmtime.Module.from_file(engine, "wasi.wasm")
 *   linker = wasmtime.Linker(engine)
 *   linker.define_wasi()
 *   store  = wasmtime.Store(engine)
 *   linker.define_wasi_instance(store)
 *   instance = linker.instantiate(store, module)
 *
 *   # IMPORTANT: do NOT call the exported "_start".  Call wasi_init() once,
 *   # then wasi_tick() at ~60 Hz.  Read the framebuffer via wasi_fb_ptr().
 *
 * Exported API:
 *   void   wasi_init(void)                      - load ROMs, reset CPU
 *   void   wasi_tick(void)                      - run one emulator frame
 *   int    wasi_keydown(int sdl_sym)            - inject key press
 *   int    wasi_keyup(int sdl_sym)              - inject key release
 *   int    wasi_fb_ptr(void)                    - address of g_fb in linear mem
 *   int    wasi_fb_width(void)                  - 280
 *   int    wasi_fb_height(void)                 - 192
 *   int    wasi_beep_pending(void)              - 1 if speaker clicked
 *   void   wasi_ack_beep(void)                  - clear beep flag
 *   void   wasi_dump_fb(void)                   - write raw RGBA framebuffer to stdout
 *   int    wasi_insertFloppy(const uint8_t*,int,int)
 */

#include <stdio.h>
#include <string.h>
#include <stdbool.h>

#include "puce6502.h"
#include "wasi_fonts.h"
#include "wasi_roms.h"

typedef unsigned int uint32_t;

/*===========================================================================
 * SDL keycodes (matching pygame / SDL2 so the Python host can pass
 * pygame.event.key values straight through).  We no longer link SDL2.
 *=========================================================================*/
#define SDLK_SCANCODE_MASK  (1 << 30)

#define SDLK_a 97
#define SDLK_b 98
#define SDLK_c 99
#define SDLK_d 100
#define SDLK_e 101
#define SDLK_f 102
#define SDLK_g 103
#define SDLK_h 104
#define SDLK_i 105
#define SDLK_j 106
#define SDLK_k 107
#define SDLK_l 108
#define SDLK_m 109
#define SDLK_n 110
#define SDLK_o 111
#define SDLK_p 112
#define SDLK_q 113
#define SDLK_r 114
#define SDLK_s 115
#define SDLK_t 116
#define SDLK_u 117
#define SDLK_v 118
#define SDLK_w 119
#define SDLK_x 120
#define SDLK_y 121
#define SDLK_z 122
#define SDLK_LEFTBRACKET  '['
#define SDLK_BACKSLASH    '\\'
#define SDLK_RIGHTBRACKET ']'
#define SDLK_BACKSPACE    8
#define SDLK_0 '0'
#define SDLK_1 '1'
#define SDLK_2 '2'
#define SDLK_3 '3'
#define SDLK_4 '4'
#define SDLK_5 '5'
#define SDLK_6 '6'
#define SDLK_7 '7'
#define SDLK_8 '8'
#define SDLK_9 '9'
#define SDLK_QUOTE     '\''
#define SDLK_EQUALS    '='
#define SDLK_SEMICOLON ';'
#define SDLK_COMMA     ','
#define SDLK_PERIOD    '.'
#define SDLK_SLASH     '/'
#define SDLK_MINUS     '-'
#define SDLK_BACKQUOTE '`'
#define SDLK_SPACE     32
#define SDLK_ESCAPE    27
#define SDLK_RETURN    13

#define SDLK_LEFT   (SDLK_SCANCODE_MASK | 80)
#define SDLK_RIGHT  (SDLK_SCANCODE_MASK | 79)

#define SDLK_LSHIFT (SDLK_SCANCODE_MASK | 225)
#define SDLK_RSHIFT (SDLK_SCANCODE_MASK | 229)
#define SDLK_LCTRL  (SDLK_SCANCODE_MASK | 224)
#define SDLK_RCTRL  (SDLK_SCANCODE_MASK | 228)
#define SDLK_LALT   (SDLK_SCANCODE_MASK | 226)
#define SDLK_RALT   (SDLK_SCANCODE_MASK | 230)

#define SDLK_F1   (SDLK_SCANCODE_MASK | 58)
#define SDLK_F7   (SDLK_SCANCODE_MASK | 64)
#define SDLK_F10  (SDLK_SCANCODE_MASK | 67)
#define SDLK_F11  (SDLK_SCANCODE_MASK | 68)

#define SDLK_KP_1 (SDLK_SCANCODE_MASK | 89)
#define SDLK_KP_2 (SDLK_SCANCODE_MASK | 90)
#define SDLK_KP_3 (SDLK_SCANCODE_MASK | 91)
#define SDLK_KP_5 (SDLK_SCANCODE_MASK | 93)


/*===========================================================================
 * MEMORY LAYOUT
 *=========================================================================*/
#define RAMSIZE  0xC000
#define ROMSTART 0xD000
#define ROMSIZE  0x3000
uint8_t ram[RAMSIZE];
uint8_t rom[ROMSIZE];

#define LGCSTART 0xD000
#define LGCSIZE  0x3000
#define BK2START 0xD000
#define BK2SIZE  0x1000
uint8_t lgc[LGCSIZE];
uint8_t bk2[BK2SIZE];

#define SL6START 0xC600
#define SL6SIZE  0x0100
uint8_t sl6[SL6SIZE];

#define SL3START   0xC300
#define SL3SIZE    0x0100
#define SL3IOSTART 0xC0B0
uint8_t slot3[SL3SIZE];

static bool g_printerOnline = false;

static void initPrinterCard(void) {
    memset(slot3, 0xFF, sizeof(slot3));
    slot3[0x00] = 0x8D; /* STA $C0B0 */
    slot3[0x01] = 0xB0;
    slot3[0x02] = 0xC0;
    slot3[0x03] = 0x60; /* RTS */
}

static void printerWriteByte(uint8_t value) {
    static bool previousWasCR = false;
    if (!g_printerOnline) return;
    uint8_t c = value & 0x7F;
    if (c == '\r') { fputc('\n', stdout); previousWasCR = true; }
    else if (c == '\n') { if (!previousWasCR) fputc('\n', stdout); previousWasCR = false; }
    else { previousWasCR = false; if (c >= 0x20 && c < 0x7F) fputc(c, stdout); }
}


/*===========================================================================
 * SOFT SWITCHES / STATE
 *=========================================================================*/
uint8_t KBD   = 0;
bool TEXT  = true;
bool MIXED = false;
bool PAGE2 = false;
bool HIRES = false;
bool LCWR  = true;
bool LCRD  = false;
bool LCBK2 = true;
bool LCWFF = false;

uint8_t PB0 = 0;
uint8_t PB1 = 0;
uint8_t PB2 = 0;
float GCP[2]     = { 127.0f, 127.0f };
float GCC[2]     = { 0.0f };
int GCD[2]       = { 0 };
int GCA[2]       = { 0 };
uint8_t GCActionSpeed  = 8;
uint8_t GCReleaseSpeed = 8;
long long int GCCrigger;

static inline void resetPaddles(void) {
    GCC[0] = GCP[0] * GCP[0];
    GCC[1] = GCP[1] * GCP[1];
    GCCrigger = ticks;
}

static inline uint8_t readPaddle(int pdl) {
    const float GCFreq = 6.6f;
    GCC[pdl] -= (ticks - GCCrigger) / GCFreq;
    if (GCC[pdl] <= 0) return (GCC[pdl] = 0);
    return 0x80;
}


/*===========================================================================
 * AUDIO — beep flag for Python host to play
 *=========================================================================*/
static bool g_beepPending = false;

static void playSound(void) {
     g_beepPending = true;
}

int wasi_beep_pending(void) { return g_beepPending ? 1 : 0; }
void wasi_ack_beep(void)    { g_beepPending = false; }


/*===========================================================================
 * DISK ][
 *=========================================================================*/
int curDrv = 0;

struct drive {
    char     filename[400];
    bool     readOnly;
    uint8_t  data[232960];
    bool     motorOn;
    bool     writeMode;
    uint8_t  track;
    uint16_t nibble;
} disk[2] = { 0 };

int wasi_insertFloppy(const uint8_t *data, int size, int drv) {
    if (!data || drv < 0 || drv > 1 || size != 232960) return 0;
    memcpy(disk[drv].data, data, 232960);
    disk[drv].motorOn  = false;
    disk[drv].nibble   = 0;
    disk[drv].track    = 0;
    disk[drv].readOnly = false;
    sprintf(disk[drv].filename, "disk%d.nib", drv);
    return 1;
}

void stepMotor(uint16_t address) {
    static bool phases[2][4]   = { 0 };
    static bool phasesB[2][4]  = { 0 };
    static bool phasesBB[2][4] = { 0 };
    static int pIdx[2]     = { 0 };
    static int pIdxB[2]    = { 0 };
    static int halfTrackPos[2] = { 0 };

    address &= 7;
    int phase = address >> 1;

    phasesBB[curDrv][pIdxB[curDrv]] = phasesB[curDrv][pIdxB[curDrv]];
    phasesB[curDrv][pIdx[curDrv]]   = phases[curDrv][pIdx[curDrv]];
    pIdxB[curDrv] = pIdx[curDrv];
    pIdx[curDrv]  = phase;

    if (!(address & 1)) { phases[curDrv][phase] = false; return; }

    if ((phasesBB[curDrv][(phase + 1) & 3]) && (--halfTrackPos[curDrv] < 0))
        halfTrackPos[curDrv] = 0;

    if ((phasesBB[curDrv][(phase - 1) & 3]) && (++halfTrackPos[curDrv] > 140))
        halfTrackPos[curDrv] = 140;

    phases[curDrv][phase] = true;
    disk[curDrv].track = (halfTrackPos[curDrv] + 1) / 2;
}

static inline void setDrv(int drv) {
    disk[drv].motorOn = disk[!drv].motorOn || disk[drv].motorOn;
    disk[!drv].motorOn = false;
    curDrv = drv;
}

uint8_t softSwitches(uint16_t address, uint8_t value, bool WRT) {
    static uint8_t dLatch = 0;
    switch (address) {
    case 0xC000: return KBD;
    case 0xC010: KBD &= 0x7F; return KBD;
    case 0xC020:
    case 0xC030:
    case 0xC033: playSound(); break;
    case 0xC050: TEXT  = false; break;
    case 0xC051: TEXT  = true;  break;
    case 0xC052: MIXED = false; break;
    case 0xC053: MIXED = true;  break;
    case 0xC054: PAGE2 = false; break;
    case 0xC055: PAGE2 = true;  break;
    case 0xC056: HIRES = false; break;
    case 0xC057: HIRES = true;  break;
    case 0xC061: return PB0;
    case 0xC062: return PB1;
    case 0xC063: return PB2;
    case 0xC064: return readPaddle(0);
    case 0xC065: return readPaddle(1);
    case 0xC070: resetPaddles(); break;
    case SL3IOSTART:
        if (WRT) printerWriteByte(value);
        return 0;
    case SL3IOSTART + 1:
        return g_printerOnline ? 0x80 : 0x00;
    case 0xC080: LCBK2 = 1; LCRD = 1; LCWR = 0;      LCWFF = 0;    break;
    case 0xC081:
    case 0xC085: LCBK2 = 1; LCRD = 0; LCWR |= LCWFF; LCWFF = !WRT; break;
    case 0xC082:
    case 0xC086: LCBK2 = 1; LCRD = 0; LCWR = 0;      LCWFF = 0;    break;
    case 0xC083:
    case 0xC087: LCBK2 = 1; LCRD = 1; LCWR |= LCWFF; LCWFF = !WRT; break;
    case 0xC088:
    case 0xC08C: LCBK2 = 0; LCRD = 1; LCWR = 0;      LCWFF = 0;    break;
    case 0xC089:
    case 0xC08D: LCBK2 = 0; LCRD = 0; LCWR |= LCWFF; LCWFF = !WRT; break;
    case 0xC08A:
    case 0xC08E: LCBK2 = 0; LCRD = 0; LCWR = 0;      LCWFF = 0;    break;
    case 0xC08B:
    case 0xC08F: LCBK2 = 0; LCRD = 1; LCWR |= LCWFF; LCWFF = !WRT; break;
    case 0xC0E0: case 0xC0E1: case 0xC0E2: case 0xC0E3:
    case 0xC0E4: case 0xC0E5: case 0xC0E6: case 0xC0E7:
        stepMotor(address); break;
    case 0xCFFF:
    case 0xC0E8: disk[curDrv].motorOn = false; break;
    case 0xC0E9: disk[curDrv].motorOn = true;  break;
    case 0xC0EA: setDrv(0); break;
    case 0xC0EB: setDrv(1); break;
    case 0xC0EC:
        if (disk[curDrv].writeMode)
            disk[curDrv].data[disk[curDrv].track * 0x1A00 + disk[curDrv].nibble] = dLatch;
        else
            dLatch = disk[curDrv].data[disk[curDrv].track * 0x1A00 + disk[curDrv].nibble];
        disk[curDrv].nibble = (disk[curDrv].nibble + 1) % 0x1A00;
        return dLatch;
    case 0xC0ED: dLatch = value; break;
    case 0xC0EE:
        disk[curDrv].writeMode = false;
        return disk[curDrv].readOnly ? 0x80 : 0;
    case 0xC0EF: disk[curDrv].writeMode = true; break;
    }
    return ticks & 0xFF;
}

uint8_t readMem(uint16_t address) {
    if (address < RAMSIZE) return ram[address];
    if (address >= ROMSTART) {
        if (!LCRD) return rom[address - ROMSTART];
        if (LCBK2 && (address < 0xE000)) return bk2[address - BK2START];
        return lgc[address - LGCSTART];
    }
    if ((address & 0xFF00) == SL6START) return sl6[address - SL6START];
    if ((address & 0xFF00) == SL3START) return slot3[address - SL3START];
    if ((address & 0xF000) == 0xC000) return softSwitches(address, 0, false);
    return ticks & 0xFF;
}

void writeMem(uint16_t address, uint8_t value) {
    if (address < RAMSIZE) { ram[address] = value; return; }
    if ((address & 0xFF00) == SL3START) return;
    if (LCWR && (address >= ROMSTART)) {
        if (LCBK2 && (address < 0xE000)) { bk2[address - BK2START] = value; return; }
        lgc[address - LGCSTART] = value;
        return;
    }
    if ((address & 0xF000) == 0xC000) { softSwitches(address, value, true); return; }
}


/*===========================================================================
 * FRAMEBUFFER — 280x192 RGBA32 (ABGR8888 little-endian in linear memory,
 * so Python sees R,G,B,A per pixel when reading raw bytes).
 *=========================================================================*/
#define FB_W  280
#define FB_H  192

static uint32_t g_fb[FB_W * FB_H];

int  wasi_fb_ptr(void)    { return (int)(size_t)g_fb; }
int  wasi_fb_width(void)  { return FB_W; }
int  wasi_fb_height(void) { return FB_H; }

/* Dump the raw framebuffer pixels to stdout as 280x192 RGBA bytes.
 * The Python host can capture this with --dump-fb for debugging. */
void wasi_dump_fb(void) {
    const uint8_t *fb = (const uint8_t *)g_fb;
    size_t total = FB_W * FB_H * 4;
    fwrite(fb, 1, total, stdout);
    fflush(stdout);
}

/* Build an ABGR8888 value from RGB components.  Stored little-endian the
 * byte order in memory is R,G,B,A — exactly what Python's "RGBA" expects. */
#define MKPIXEL(r, g, b) \
    (((uint32_t)0xFFu << 24) | ((uint32_t)(b) << 16) | ((uint32_t)(g) << 8) | (uint32_t)(r))
static inline uint32_t mkPixel(uint8_t r, uint8_t g, uint8_t b) {
    return MKPIXEL(r, g, b);
}

static inline void setPixel(int x, int y, uint32_t c) {
    if (x < 0 || x >= FB_W || y < 0 || y >= FB_H) return;
    g_fb[y * FB_W + x] = c;
}

static void fillRect(int x, int y, int w, int h, uint32_t c) {
    for (int j = 0; j < h; j++)
        for (int i = 0; i < w; i++)
            setPixel(x + i, y + j, c);
}

/*===========================================================================
 * PALETTES — Apple II colors (same values as the SDL build)
 *=========================================================================*/
static const uint32_t g_color[16] = {
    MKPIXEL(  0,   0,   0), MKPIXEL(226,  57,  86), MKPIXEL( 28, 116, 205),
    MKPIXEL(126, 110, 173), MKPIXEL( 31, 129, 128), MKPIXEL(137, 130, 122),
    MKPIXEL( 86, 168, 228), MKPIXEL(144, 178, 223), MKPIXEL(151,  88,  34),
    MKPIXEL(234, 108,  21), MKPIXEL(158, 151, 143), MKPIXEL(255, 206, 240),
    MKPIXEL(144, 192,  49), MKPIXEL(255, 253, 166), MKPIXEL(159, 210, 213),
    MKPIXEL(255, 255, 255)
};

static const uint32_t g_hcolor[16] = {
    MKPIXEL(  0,   0,   0), MKPIXEL(144, 192,  49), MKPIXEL(126, 110, 173),
    MKPIXEL(255, 255, 255), MKPIXEL(  0,   0,   0), MKPIXEL(234, 108,  21),
    MKPIXEL( 86, 168, 228), MKPIXEL(255, 255, 255), MKPIXEL(  0,   0,   0),
    MKPIXEL( 63,  55,  86), MKPIXEL( 72,  96,  25), MKPIXEL(255, 255, 255),
    MKPIXEL(  0,   0,   0), MKPIXEL( 43,  84, 114), MKPIXEL(117,  54,  10),
    MKPIXEL(255, 255, 255)
};


/*===========================================================================
 * VIDEO ADDRESS TABLES
 *=========================================================================*/
static const int offsetGR[24] = {
    0x0000, 0x0080, 0x0100, 0x0180, 0x0200, 0x0280, 0x0300, 0x0380,
    0x0028, 0x00A8, 0x0128, 0x01A8, 0x0228, 0x02A8, 0x0328, 0x03A8,
    0x0050, 0x00D0, 0x0150, 0x01D0, 0x0250, 0x02D0, 0x0350, 0x03D0
};
static const int offsetHGR[192] = {
    0x0000, 0x0400, 0x0800, 0x0C00, 0x1000, 0x1400, 0x1800, 0x1C00,
    0x0080, 0x0480, 0x0880, 0x0C80, 0x1080, 0x1480, 0x1880, 0x1C80,
    0x0100, 0x0500, 0x0900, 0x0D00, 0x1100, 0x1500, 0x1900, 0x1D00,
    0x0180, 0x0580, 0x0980, 0x0D80, 0x1180, 0x1580, 0x1980, 0x1D80,
    0x0200, 0x0600, 0x0A00, 0x0E00, 0x1200, 0x1600, 0x1A00, 0x1E00,
    0x0280, 0x0680, 0x0A80, 0x0E80, 0x1280, 0x1680, 0x1A80, 0x1E80,
    0x0300, 0x0700, 0x0B00, 0x0F00, 0x1300, 0x1700, 0x1B00, 0x1F00,
    0x0380, 0x0780, 0x0B80, 0x0F80, 0x1380, 0x1780, 0x1B80, 0x1F80,
    0x0028, 0x0428, 0x0828, 0x0C28, 0x1028, 0x1428, 0x1828, 0x1C28,
    0x00A8, 0x04A8, 0x08A8, 0x0CA8, 0x10A8, 0x14A8, 0x18A8, 0x1CA8,
    0x0128, 0x0528, 0x0928, 0x0D28, 0x1128, 0x1528, 0x1928, 0x1D28,
    0x01A8, 0x05A8, 0x09A8, 0x0DA8, 0x11A8, 0x15A8, 0x19A8, 0x1DA8,
    0x0228, 0x0628, 0x0A28, 0x0E28, 0x1228, 0x1628, 0x1A28, 0x1E28,
    0x02A8, 0x06A8, 0x0AA8, 0x0EA8, 0x12A8, 0x16A8, 0x1AA8, 0x1EA8,
    0x0328, 0x0728, 0x0B28, 0x0F28, 0x1328, 0x1728, 0x1B28, 0x1F28,
    0x03A8, 0x07A8, 0x0BA8, 0x0FA8, 0x13A8, 0x17A8, 0x1BA8, 0x1FA8,
    0x0050, 0x0450, 0x0850, 0x0C50, 0x1050, 0x1450, 0x1850, 0x1C50,
    0x00D0, 0x04D0, 0x08D0, 0x0CD0, 0x10D0, 0x14D0, 0x18D0, 0x1CD0,
    0x0150, 0x0550, 0x0950, 0x0D50, 0x1150, 0x1550, 0x1950, 0x1D50,
    0x01D0, 0x05D0, 0x09D0, 0x0DD0, 0x11D0, 0x15D0, 0x19D0, 0x1DD0,
    0x0250, 0x0650, 0x0A50, 0x0E50, 0x1250, 0x1650, 0x1A50, 0x1E50,
    0x02D0, 0x06D0, 0x0AD0, 0x0ED0, 0x12D0, 0x16D0, 0x1AD0, 0x1ED0,
    0x0350, 0x0750, 0x0B50, 0x0F50, 0x1350, 0x1750, 0x1B50, 0x1F50,
    0x03D0, 0x07D0, 0x0BD0, 0x0FD0, 0x13D0, 0x17D0, 0x1BD0, 0x1FD0
};


/*===========================================================================
 * RENDERING — writes directly into g_fb[]
 *=========================================================================*/
enum characterAttribute { A_NORMAL, A_INVERSE, A_FLASH };
static uint8_t flashCycle = 0;

/* Blit one 7x8 glyph into the framebuffer.
 * glyphIndex 0..127.  inverse selects the reverse font (inverted video).
 * The BMP is stored bottom-up, so image row 0 = file row 7. */
static void blitChar(int x, int y, int glyphIndex, bool inverse,
                     uint32_t fgColor, uint32_t bgColor) {
    const unsigned char *fontBits = inverse ? g_fontReverseBits : g_fontNormalBits;
    for (int row = 0; row < 8; row++) {
        int fileRow = 7 - row;          /* top-down -> bottom-up */
        for (int col = 0; col < 7; col++) {
            int bitIdx = fileRow * 896 + glyphIndex * 7 + col;
            bool pixel = (fontBits[bitIdx >> 3] >> (7 - (bitIdx & 7))) & 1;
            setPixel(x + col, y + row, pixel ? fgColor : bgColor);
        }
    }
}

static void renderVideo(void) {
    static int TextCache[24][40];
    static int LoResCache[24][40];
    static int HiResCache[192][40];
    static uint8_t previousBit[192][40];
    static bool prevTEXT   = true;
    static bool prevMIXED  = false;
    static bool prevPAGE2  = false;
    static bool prevHIRES  = false;

    if (prevTEXT != TEXT || prevMIXED != MIXED ||
        prevPAGE2 != PAGE2 || prevHIRES != HIRES) {
        memset(TextCache,  -1, sizeof(TextCache));
        memset(LoResCache, -1, sizeof(LoResCache));
        memset(HiResCache,-1, sizeof(HiResCache));
        memset(previousBit, 0, sizeof(previousBit));
        prevTEXT  = TEXT;
        prevMIXED = MIXED;
        prevPAGE2 = PAGE2;
        prevHIRES = HIRES;
    }

    /* Clear to black */
    for (int i = 0; i < FB_W * FB_H; i++) g_fb[i] = g_color[0];

    /* ---- HIGH RES GRAPHICS ---- */
    if (!TEXT && HIRES) {
        uint16_t word;
        uint8_t bits[16], bit, pbit, colorSet, even;
        uint16_t vRamBase = 0x2000 + PAGE2 * 0x2000;
        uint8_t lastLine = MIXED ? 160 : 192;
        for (int line = 0; line < lastLine; line++) {
            for (int col = 0; col < 40; col += 2) {
                int x = col * 7;
                even = 0;

                word = ((uint16_t)(ram[vRamBase + offsetHGR[line] + col + 1]) << 8)
                     | ram[vRamBase + offsetHGR[line] + col];

                if (HiResCache[line][col] != word || !flashCycle) {
                    for (bit = 0; bit < 16; bit++)
                        bits[bit] = (word >> bit) & 1;
                    colorSet = bits[7] * 4;
                    pbit = previousBit[line][col];
                    bit = 0;
                    while (bit < 15) {
                        if (bit == 7) { colorSet = bits[15] * 4; bit++; }
                        uint8_t ci = even + colorSet + (bits[bit] << 1) + pbit;
                        setPixel(x, line, g_hcolor[ci]);
                        x++;
                        pbit = bits[bit++];
                        even = even ? 0 : 8;
                    }
                    HiResCache[line][col] = word;
                    if ((col < 37) && (previousBit[line][col + 2] != pbit)) {
                        previousBit[line][col + 2] = pbit;
                        HiResCache[line][col + 2] = -1;
                    }
                }
            }
        }
    }
    /* ---- LOW RES GRAPHICS ---- */
    else if (!TEXT) {
        uint16_t vRamBase = 0x400 + PAGE2 * 0x0400;
        uint8_t lastLine = MIXED ? 20 : 24;
        for (int col = 0; col < 40; col++) {
            int pxX = col * 7;
            for (int line = 0; line < lastLine; line++) {
                int pxY = line * 8;
                uint8_t glyph = ram[vRamBase + offsetGR[line] + col];
                if (LoResCache[line][col] != glyph || !flashCycle) {
                    LoResCache[line][col] = glyph;
                    fillRect(pxX, pxY, 7, 4, g_color[glyph >> 4]);
                    fillRect(pxX, pxY + 4, 7, 4, g_color[glyph & 0x0F]);
                }
            }
        }
    }

    /* ---- TEXT 40 COLUMNS ---- */
    if (TEXT || MIXED) {
        uint16_t vRamBase = 0x400 + PAGE2 * 0x0400;
        uint8_t firstLine = TEXT ? 0 : 20;
        for (int col = 0; col < 40; col++) {
            int dstX = col * 7;
            for (int line = firstLine; line < 24; line++) {
                int dstY = line * 8;
                uint8_t glyph = ram[vRamBase + offsetGR[line] + col];

                enum characterAttribute attr =
                    (glyph > 0x7F) ? A_NORMAL :
                    (glyph < 0x40) ? A_INVERSE : A_FLASH;

                TextCache[line][col] = glyph;
                glyph &= 0x7F;
                if (glyph > 0x5F) glyph &= 0x3F;
                if (glyph < 0x20) glyph |= 0x40;

                bool inverse = (attr == A_INVERSE) ||
                    (attr == A_FLASH && flashCycle >= 15);
                uint32_t fg = inverse ? g_color[0] : g_color[15];
                uint32_t bg = inverse ? g_color[15] : g_color[0];

                blitChar(dstX, dstY, glyph & 0x7F, inverse, fg, bg);
            }
        }
    }

    /* ---- DISK STATUS LEDS ---- */
    if (disk[curDrv].motorOn) {
        int lx = (curDrv == 0) ? 272 : 276;
        fillRect(lx, FB_H - 4, 4, 4,
                 disk[curDrv].writeMode ? mkPixel(255,0,0) : mkPixel(0,255,0));
    }

    if (++flashCycle == 30) flashCycle = 0;
}


/*===========================================================================
 * INPUT — key state array + mapping to Apple II KBD register
 *=========================================================================*/
static bool g_ctrl  = false;
static bool g_shift = false;
static bool g_alt   = false;
static bool g_paused = false;

static void updateModifiers(void) {
    PB0 = g_alt   ? 0xFF : 0x00;
    PB1 = g_ctrl  ? 0xFF : 0x00;
    PB2 = g_shift ? 0xFF : 0x00;
}

int wasi_keydown(int sdl_sym) {
    switch (sdl_sym) {
    case SDLK_LCTRL: case SDLK_RCTRL: g_ctrl = true;  updateModifiers(); return 1;
    case SDLK_LSHIFT:case SDLK_RSHIFT:g_shift = true; updateModifiers(); return 1;
    case SDLK_LALT:  case SDLK_RALT:  g_alt = true;   updateModifiers(); return 1;
    default: break;
    }

    bool ctrl  = g_ctrl;
    bool shift = g_shift;
    bool alt   = g_alt;

    PB0 = alt   ? 0xFF : 0x00;
    PB1 = ctrl  ? 0xFF : 0x00;
    PB2 = shift ? 0xFF : 0x00;

    /* Emulator control keys */
    if (sdl_sym == SDLK_F10) { g_paused = !g_paused; return 1; }
    if (sdl_sym == SDLK_F11) { puce6502RST(); return 1; }

    /* Joystick paddle axis activation */
    switch (sdl_sym) {
    case SDLK_KP_1: GCD[0] = -1; GCA[0] = 1; return 1;
    case SDLK_KP_3: GCD[0] =  1; GCA[0] = 1; return 1;
    case SDLK_KP_5: GCD[1] = -1; GCA[1] = 1; return 1;
    case SDLK_KP_2: GCD[1] =  1; GCA[1] = 1; return 1;
    default: break;
    }

    /* Apple II keyboard mapping (matches the native SDL build) */
#define MAP_KEY(sym, code_up, code_down) \
    if (sdl_sym == (sym)) { KBD = (!ctrl) ? (code_down) : (code_up); return 1; }

    MAP_KEY(SDLK_a, 0x81, 0xC1);
    MAP_KEY(SDLK_b, 0x82, 0xC2);
    MAP_KEY(SDLK_c, 0x83, 0xC3);
    MAP_KEY(SDLK_d, 0x84, 0xC4);
    MAP_KEY(SDLK_e, 0x85, 0xC5);
    MAP_KEY(SDLK_f, 0x86, 0xC6);
    MAP_KEY(SDLK_g, 0x87, 0xC7);
    MAP_KEY(SDLK_h, 0x88, 0xC8);
    MAP_KEY(SDLK_i, 0x89, 0xC9);
    MAP_KEY(SDLK_j, 0x8A, 0xCA);
    MAP_KEY(SDLK_k, 0x8B, 0xCB);
    MAP_KEY(SDLK_l, 0x8C, 0xCC);
    if (sdl_sym == SDLK_m) {
        if (shift) KBD = 0x9D; else KBD = ctrl ? 0x8D : 0xCD; return 1;
    }
    if (sdl_sym == SDLK_n) {
        if (shift) KBD = 0x9E; else KBD = ctrl ? 0x8E : 0xCE; return 1;
    }
    MAP_KEY(SDLK_o, 0x8F, 0xCF);
    if (sdl_sym == SDLK_p) {
        if (shift)      KBD = 0x80;
        else if (!ctrl) KBD = 0x90;
        else            KBD = 0xD0;
        return 1;
    }
    MAP_KEY(SDLK_q, 0x91, 0xD1);
    MAP_KEY(SDLK_r, 0x92, 0xD2);
    MAP_KEY(SDLK_s, 0x93, 0xD3);
    MAP_KEY(SDLK_t, 0x94, 0xD4);
    MAP_KEY(SDLK_u, 0x95, 0xD5);
    MAP_KEY(SDLK_v, 0x96, 0xD6);
    MAP_KEY(SDLK_w, 0x97, 0xD7);
    MAP_KEY(SDLK_x, 0x98, 0xD8);
    MAP_KEY(SDLK_y, 0x99, 0xD9);
    MAP_KEY(SDLK_z, 0x9A, 0xDA);
    MAP_KEY(SDLK_LEFTBRACKET,  0x9B, 0xDB);
    MAP_KEY(SDLK_BACKSLASH,    0x9C, 0xDC);
    MAP_KEY(SDLK_RIGHTBRACKET, 0x9D, 0xDD);
    MAP_KEY(SDLK_BACKSPACE,    0xDF, 0x88);
    if (sdl_sym == SDLK_0) KBD = shift ? 0xA9 : 0xB0;
    if (sdl_sym == SDLK_1) KBD = shift ? 0xA1 : 0xB1;
    if (sdl_sym == SDLK_2) KBD = shift ? 0xC0 : 0xB2;
    if (sdl_sym == SDLK_3) KBD = shift ? 0xA3 : 0xB3;
    if (sdl_sym == SDLK_4) KBD = shift ? 0xA4 : 0xB4;
    if (sdl_sym == SDLK_5) KBD = shift ? 0xA5 : 0xB5;
    if (sdl_sym == SDLK_6) KBD = shift ? 0xDE : 0xB6;
    if (sdl_sym == SDLK_7) KBD = shift ? 0xA6 : 0xB7;
    if (sdl_sym == SDLK_8) KBD = shift ? 0xAA : 0xB8;
    if (sdl_sym == SDLK_9) KBD = shift ? 0xA8 : 0xB9;
    MAP_KEY(SDLK_QUOTE,     0xA2, 0xA7);
    MAP_KEY(SDLK_EQUALS,    0xAB, 0xBD);
    MAP_KEY(SDLK_SEMICOLON, 0xBA, 0xBB);
    MAP_KEY(SDLK_COMMA,     0xBC, 0xAC);
    MAP_KEY(SDLK_PERIOD,    0xBE, 0xAE);
    MAP_KEY(SDLK_SLASH,     0xBF, 0xAF);
    MAP_KEY(SDLK_MINUS,     0xDF, 0xAD);
    MAP_KEY(SDLK_BACKQUOTE, 0xFE, 0xE0);
    if (sdl_sym == SDLK_LEFT)   { KBD = 0x88; return 1; }
    if (sdl_sym == SDLK_RIGHT)  { KBD = 0x95; return 1; }
    if (sdl_sym == SDLK_SPACE)  { KBD = 0xA0; return 1; }
    if (sdl_sym == SDLK_ESCAPE) { KBD = 0x9B; return 1; }
    if (sdl_sym == SDLK_RETURN) { KBD = 0x8D; return 1; }
#undef MAP_KEY

    return 1;
}

int wasi_keyup(int sdl_sym) {
    switch (sdl_sym) {
    case SDLK_LCTRL: case SDLK_RCTRL: g_ctrl = false; updateModifiers(); break;
    case SDLK_LSHIFT:case SDLK_RSHIFT:g_shift = false; updateModifiers(); break;
    case SDLK_LALT:  case SDLK_RALT:  g_alt = false;   updateModifiers(); break;
    default: break;
    }

    switch (sdl_sym) {
    case SDLK_KP_1: GCD[0] = -1; GCA[0] = 0; break;
    case SDLK_KP_3: GCD[0] =  1; GCA[0] = 0; break;
    case SDLK_KP_5: GCD[1] = -1; GCA[1] = 0; break;
    case SDLK_KP_2: GCD[1] =  1; GCA[1] = 0; break;
    default: break;
    }
    return 1;
}


/*===========================================================================
 * FRAME LOOP — called by Python host at ~60 Hz
 *=========================================================================*/
void wasi_tick(void) {
    if (!g_paused) {
        puce6502Exec(17050);   /* ~1/60 s of Apple II time */
        for (uint8_t tries = 0; disk[curDrv].motorOn && tries < 32; tries++)
            puce6502Exec(5000);
    }

    for (int pdl = 0; pdl < 2; pdl++) {
        if (GCA[pdl]) {
            GCP[pdl] += GCD[pdl] * GCActionSpeed;
            if (GCP[pdl] > 255) GCP[pdl] = 255;
            if (GCP[pdl] < 0)   GCP[pdl] = 0;
        } else {
            GCP[pdl] += GCD[pdl] * GCReleaseSpeed;
            if (GCD[pdl] ==  1 && GCP[pdl] > 127) GCP[pdl] = 127;
            if (GCD[pdl] == -1 && GCP[pdl] < 127) GCP[pdl] = 127;
        }
    }

    renderVideo();
}


/*===========================================================================
 * INIT — load ROMs (embedded), reset CPU.  Call once before wasi_tick().
 *=========================================================================*/
void wasi_init(void) {
    memcpy(rom, g_romApple, ROMSIZE);
    memcpy(sl6, g_romDisk, 256);

    initPrinterCard();
    puce6502RST();

    memset(g_fb, 0, sizeof(g_fb));
}

/* Kept for STANDALONE_WASM's _start; the Python host should NOT call _start
 * directly — it calls wasi_init() + wasi_tick() instead. */
int main(void) {
    wasi_init();
    return 0;
}
