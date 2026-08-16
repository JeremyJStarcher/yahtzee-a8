; ============================================================================
; MIRROR FILE -- KEEP BYTE-IDENTICAL ACROSS BUILD TREES
; ----------------------------------------------------------------------------
; This library is intentionally duplicated because WASI ca65 can only read
; its own current directory, and kernel / user-land are separate builds:
;
;   kernel    : fconsole/bios/src/hw_limits.inc          (source of truth)
;   user-land : app/hosts/shared/hw_limits.inc           (mirror)
;
; Edit the KERNEL copy first, then sync it to the other tree.  The test
; suites run tools/inc_drift_check.py which fails if the two copies diverge.
; The bin/3rdparty/cc65-asm-tests/... copy is an independent toolchain
; fixture snapshot and is deliberately NOT kept in lockstep with these.
; ============================================================================


; CPU clock rate in cycles per second / Hz.
; Example: Atari NTSC-ish clock:
; CLOCK_SPEED = 1789773


CLOCK_SPEED = 3000000
SCREEN_COLS =  40
SCREEN_ROWS =  24
SCREEN_SIZE = SCREEN_COLS * SCREEN_ROWS

START_REGION_CHAR_RAM = $A000
END_REGION_CHAR_RAM = START_REGION_CHAR_RAM + SCREEN_SIZE

START_REGION_COLOR_RAM = $B000
END_REGION_COLOR_RAM = START_REGION_COLOR_RAM + SCREEN_SIZE

DEFAULT_COLOR = $6F
DEFAULT_SCREEN_CHAR = 181
