#!/usr/bin/env python3
"""reinette_host.py — Python host for the headless Reinette II+ WASI module.

Loads wasi.wasm with wasmtime, drives the Apple II emulator at ~60 Hz, reads the
280x192 RGBA framebuffer from WASM linear memory, and displays it with either:

    pygame    -- interactive scaled window (default)
    terminal  -- curses + ANSI truecolor half-block output (no GUI needed)

Usage:
    python3 reinette_host.py [--renderer pygame|terminal] [--scale 3]
                             [--floppy 'DOS 3.3.nib'] [--fps 60]

The wasmtime package is expected either in the environment or in the private
site-packages directory .runtime/site-packages (installed via pip --target).
"""

from __future__ import annotations

import argparse
import curses
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# wasmtime bootstrap (mirrors bin/run_wasi.py in the parent repo)
# ---------------------------------------------------------------------------

_RUNTIME_SP = Path(__file__).resolve().parent / ".runtime" / "site-packages"
if _RUNTIME_SP.is_dir() and str(_RUNTIME_SP) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_SP))

import wasmtime  # noqa: E402

# ---------------------------------------------------------------------------
# SDL keycodes matching the SDLK_* constants in reinette-wasi.c
# ---------------------------------------------------------------------------

_MASK = 1 << 30  # SDLK_SCANCODE_MASK

SDLK_LEFT      = _MASK | 80
SDLK_RIGHT     = _MASK | 79
SDLK_LSHIFT    = _MASK | 225
SDLK_RSHIFT    = _MASK | 229
SDLK_LCTRL     = _MASK | 224
SDLK_RCTRL     = _MASK | 228
SDLK_F1        = _MASK | 58
SDLK_F7        = _MASK | 64
SDLK_F10       = _MASK | 67
SDLK_F11       = _MASK | 68

SDLK_BACKSPACE = 8
SDLK_ESCAPE    = 27
SDLK_RETURN    = 13
SDLK_SPACE     = 32

# Printable characters whose Apple II keycode is the plain (unshifted) key.
# Uppercase letters must be sent as their lowercase base key: the Apple II
# keyboard reports uppercase for both, and reinette-wasi.c only maps SDLK_a..z.
_UNSHIFTED = {
    **{chr(c): c for c in range(ord("a"), ord("z") + 1)},
    **{chr(c): c for c in range(ord("0"), ord("9") + 1)},
    " ": 32,
    "[": 91, "\\": 92, "]": 93, "'": 39, "=": 61, ";": 59,
    ",": 44, ".": 46, "/": 47, "-": 45, "`": 96,
}

# Shifted symbols -> base key that produces them (host presses Shift first).
_SHIFTED = {
    "!": ord("1"), "@": ord("2"), "#": ord("3"), "$": ord("4"), "%": ord("5"),
    "^": ord("6"), "&": ord("7"), "*": ord("8"), "(": ord("9"), ")": ord("0"),
    "_": ord("-"), "+": ord("="), "{": ord("["), "}": ord("]"), "|": ord("\\"),
    ":": ord(";"), '"': ord("'"), "<": ord(","), ">": ord("."), "?": ord("/"),
    "~": ord("`"),
}

# Upper half-block glyph: foreground paints the top 2px, background the bottom.
_HALF_BLOCK = "\u2580"


# ---------------------------------------------------------------------------
# Emulator binding
# ---------------------------------------------------------------------------

class Emulator:
    """Thin wrapper around the exported wasi_* functions of wasi.wasm."""

    FB_W = 280
    FB_H = 192

    def __init__(self, module_path: str = "wasi.wasm") -> None:
        self._engine = wasmtime.Engine()
        self._store = wasmtime.Store(self._engine)
        wasi = wasmtime.WasiConfig()
        wasi.inherit_stdout()
        wasi.inherit_stderr()
        self._store.set_wasi(wasi)

        linker = wasmtime.Linker(self._engine)
        linker.define_wasi()
        module = wasmtime.Module.from_file(self._engine, module_path)
        instance = linker.instantiate(self._store, module)
        exp = instance.exports(self._store)

        self._memory = exp["memory"]
        self._init = exp["wasi_init"]
        self._tick = exp["wasi_tick"]
        self._keydown = exp["wasi_keydown"]
        self._keyup = exp["wasi_keyup"]
        self._fb_ptr = exp["wasi_fb_ptr"]
        self._fb_w = exp["wasi_fb_width"]
        self._fb_h = exp["wasi_fb_height"]
        self._beep = exp["wasi_beep_pending"]
        self._ack = exp["wasi_ack_beep"]
        self._floppy = exp["wasi_insertFloppy"]
        self._dump_fb = exp.get("wasi_dump_fb")  # optional, added in rebuilt WASM
        self._malloc = exp["malloc"]
        self._free = exp["free"]

    # -- lifecycle ----------------------------------------------------------
    def init(self) -> None:
        self._init(self._store)

    def tick(self) -> None:
        self._tick(self._store)

    # -- input ---------------------------------------------------------------
    def keydown(self, sym: int) -> None:
        self._keydown(self._store, sym)

    def keyup(self, sym: int) -> None:
        self._keyup(self._store, sym)

    def press(self, sym: int) -> None:
        """Send a single key down+up (self-cleaning, releases modifiers)."""
        self.keydown(sym)
        self.keyup(sym)

    def press_shifted(self, base_sym: int) -> None:
        """Send Shift down + base key + Shift up (for shifted symbols)."""
        self.keydown(SDLK_LSHIFT)
        self.keydown(base_sym)
        self.keyup(base_sym)
        self.keyup(SDLK_LSHIFT)

    # -- video ---------------------------------------------------------------
    def framebuffer(self) -> bytearray:
        ptr = self._fb_ptr(self._store)
        n = self.FB_W * self.FB_H * 4
        return self._memory.read(self._store, ptr, ptr + n)

    # -- audio ---------------------------------------------------------------
    def beep_pending(self) -> bool:
        return bool(self._beep(self._store))

    def ack_beep(self) -> None:
        self._ack(self._store)

    # -- floppy ---------------------------------------------------------------
    def insert_floppy(self, path: str, drive: int = 0) -> bool:
        data = Path(path).read_bytes()
        size = len(data)
        buf = self._malloc(self._store, size)
        try:
            self._memory.write(self._store, data, buf)
            return bool(self._floppy(self._store, buf, size, drive))
        finally:
            self._free(self._store, buf)

    def dump_fb(self, path: str) -> None:
        """Write the current framebuffer as a raw RGBA dump to 'path'."""
        fb = self.framebuffer()
        Path(path).write_bytes(fb)
        # Also call wasi_dump_fb if the WASM has been rebuilt with this export.
        if self._dump_fb is not None:
            self._dump_fb(self._store)


# ---------------------------------------------------------------------------
# Pygame renderer
# ---------------------------------------------------------------------------

def _pygame_beep():
    """Play a short square-wave beep; best-effort (no audio device tolerated)."""
    try:
        import pygame
        from array import array

        if not pygame.mixer.get_init():
            pygame.mixer.init()
        rate = pygame.mixer.get_init()[0]
        freq = 1000
        n = rate // 6  # ~166 ms
        buf = array("h")
        period = rate // freq
        for i in range(n):
            buf.append(12000 if (i % period) < period // 2 else -12000)
        sound = pygame.mixer.Sound(buffer=buf)
        sound.play()
    except Exception:
        pass  # audio is optional


def run_pygame(emu: Emulator, args: argparse.Namespace) -> None:
    import pygame

    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass

    scale = max(1, args.scale)
    screen = pygame.display.set_mode((emu.FB_W * scale, emu.FB_H * scale))
    pygame.display.set_caption("Reinette II+ (WASI)")
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q and (event.mod & pygame.KMOD_CTRL):
                    running = False
                else:
                    emu.keydown(event.key)
            elif event.type == pygame.KEYUP:
                emu.keyup(event.key)
            elif event.type == pygame.DROPFILE:
                try:
                    emu.insert_floppy(event.file, 0)
                except OSError as exc:
                    print(f"floppy load failed: {exc}", file=sys.stderr)

        emu.tick()

        if emu.beep_pending():
            emu.ack_beep()
            _pygame_beep()

        fb = emu.framebuffer()
        surface = pygame.image.frombuffer(fb, (emu.FB_W, emu.FB_H), "RGBA")
        scaled = pygame.transform.scale(surface, (emu.FB_W * scale, emu.FB_H * scale))
        screen.blit(scaled, (0, 0))
        pygame.display.flip()
        clock.tick(args.fps)

    pygame.quit()


# ---------------------------------------------------------------------------
# Terminal renderer (curses input + ANSI truecolor output)
# ---------------------------------------------------------------------------

def _curses_to_sdl(key) -> int | None:
    """Map a curses get_wch() result to an SDL keycode (or None if ignored)."""
    if isinstance(key, str):
        ch = key
        o = ord(ch)
        if o == 27:
            return SDLK_ESCAPE
        if o in (13, 10):
            return SDLK_RETURN
        if o in (8, 127):
            return SDLK_BACKSPACE
        if 1 <= o <= 26:  # Ctrl+letter
            return o + 96
        if 32 <= o < 127:
            return o
        return None
    # special (function/arrow) keys are integers
    if key in (curses.KEY_LEFT,):     # noqa: F821  (curses imported in run_terminal)
        return SDLK_LEFT
    if key in (curses.KEY_RIGHT,):    # noqa: F821
        return SDLK_RIGHT
    if key in (curses.KEY_BACKSPACE,):  # noqa: F821
        return SDLK_BACKSPACE
    if key in (curses.KEY_ENTER,):    # noqa: F821
        return SDLK_RETURN
    if key in (curses.KEY_F1,):       # noqa: F821
        return SDLK_F1
    if key in (curses.KEY_F7,):       # noqa: F821
        return SDLK_F7
    if key in (curses.KEY_F10,):      # noqa: F821
        return SDLK_F10
    if key in (curses.KEY_F11,):      # noqa: F821
        return SDLK_F11
    return None


def _send_char(emu: Emulator, key) -> None:
    """Forward one typed character (str or curses special key) to the emulator."""
    if isinstance(key, int):  # curses KEY_* special key
        if key in (curses.KEY_F7,):  # noqa: F821  -> host reinsert floppy
            return
        sym = _curses_to_sdl(key)
        if sym is not None:
            emu.press(sym)
        return

    ch = key
    if ch in _SHIFTED:
        emu.press_shifted(_SHIFTED[ch])
    elif ch in _UNSHIFTED:
        emu.press(_UNSHIFTED[ch])
    elif "A" <= ch <= "Z":
        # Apple II reports uppercase; send the lowercase base key.
        emu.press(ord(ch.lower()))
    elif 1 <= ord(ch) <= 26:
        # Ctrl+letter: hold ctrl, press base, release.
        base = ord(ch) + 96
        emu.keydown(SDLK_LCTRL)
        emu.keydown(base)
        emu.keyup(base)
        emu.keyup(SDLK_LCTRL)


def run_terminal(emu: Emulator, args: argparse.Namespace) -> None:
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    stdscr.nodelay(True)
    try:
        curses.curs_set(0)
    except curses.error:
        pass

    out = sys.stdout
    out.write("\x1b[?25l\x1b[2J")  # hide cursor, clear screen
    out.flush()

    prev: list[list[tuple[int, int, int]]] | None = None
    half_w = emu.FB_W // 2   # 140 cells wide
    half_h = emu.FB_H // 2   # 96 cells tall

    try:
        while True:
            # Drain all pending keys without blocking.
            while True:
                try:
                    key = stdscr.get_wch()
                except curses.error:
                    break  # no input ready
                if key == "\x1b":
                    return  # ESC quits the terminal host
                _send_char(emu, key)

            emu.tick()

            if emu.beep_pending():
                emu.ack_beep()
                out.write("\a")

            fb = emu.framebuffer()
            prev = _render_halfblocks(out, fb, prev, half_w, half_h)

            out.flush()
            time.sleep(1.0 / max(1, args.fps))
    except KeyboardInterrupt:
        pass
    finally:
        out.write("\x1b[?25h\x1b[0m\x1b[2J\x1b[H")
        out.flush()
        curses.nocbreak()
        stdscr.keypad(False)
        curses.echo()
        curses.endwin()


def _render_halfblocks(out, fb, prev, half_w, half_h):
    """Redraw only changed 2x2-pixel cells using ANSI 24-bit color."""
    changed = prev is None
    if prev is None:
        prev = [[(0, 0, 0)] * half_w for _ in range(half_h)]

    for cy in range(half_h):
        y0 = cy * 2
        y1 = y0 + 1
        for cx in range(half_w):
            x0 = cx * 2
            x1 = x0 + 1
            # Average 2x2 block: top two pixels -> fg, bottom two -> bg.
            top = _avg2(fb, x0, y0, x1, y0)
            bot = _avg2(fb, x0, y1, x1, y1)
            if prev[cy][cx] == (top, bot) and not changed:
                continue
            prev[cy][cx] = (top, bot)
            out.write(f"\x1b[{cy + 1};{cx + 1}H")
            out.write(f"\x1b[38;2;{top[0]};{top[1]};{top[2]}m")
            out.write(f"\x1b[48;2;{bot[0]};{bot[1]};{bot[2]}m")
            out.write(_HALF_BLOCK)

    out.write(f"\x1b[{half_h + 1};1H\x1b[0m")  # cursor below the picture
    out.flush()
    return prev


def _avg2(fb, x0, y0, x1, y1):
    """Average RGBA color of two adjacent pixels (stride=4, RGBA layout)."""
    i0 = (y0 * 280 + x0) * 4
    i1 = (y1 * 280 + x1) * 4
    return (
        (fb[i0] + fb[i1]) // 2,
        (fb[i0 + 1] + fb[i1 + 1]) // 2,
        (fb[i0 + 2] + fb[i1 + 2]) // 2,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Python host for the headless Reinette II+ WASI emulator."
    )
    parser.add_argument(
        "--module", default="wasi.wasm", help="path to the WASI module (default: wasi.wasm)"
    )
    parser.add_argument(
        "--renderer",
        choices=("pygame", "terminal"),
        default="pygame",
        help="display backend (default: pygame)",
    )
    parser.add_argument("--scale", type=int, default=3, help="pygame integer scale (default: 3)")
    parser.add_argument("--fps", type=int, default=60, help="target frame rate (default: 60)")
    parser.add_argument(
        "--floppy",
        action="append",
        default=[],
        metavar="FILE.nib",
        help="insert a .nib floppy into drive 0 at startup (repeatable: next goes to drive 1)",
    )
    args = parser.parse_args(argv)

    if args.renderer == "pygame":
        try:
            import pygame  # noqa: F401
        except ImportError:
            print("pygame not installed; falling back to terminal renderer.", file=sys.stderr)
            args.renderer = "terminal"

    emu = Emulator(args.module)
    emu.init()

    for i, path in enumerate(args.floppy):
        if not emu.insert_floppy(path, i % 2):
            print(f"failed to insert floppy: {path}", file=sys.stderr)

    if args.renderer == "pygame":
        run_pygame(emu, args)
    else:
        run_terminal(emu, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
