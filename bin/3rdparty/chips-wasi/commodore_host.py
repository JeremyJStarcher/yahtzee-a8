#!/usr/bin/env python3
"""commodore_host.py — Shared Python host for the VIC-20 / C64 chips WASI modules.

Loads vic20.wasm or c64.wasm with wasmtime, drives the emulator at ~60 Hz,
reads the RGBA32 framebuffer from WASM linear memory, and displays it with
pygame.  Also supports headless operation (--frames / --dump / --preview /
--type) for automated validation without a display.

The thin wrapper scripts vic20_host.py and c64_host.py just call main() with
the correct module path and framebuffer dimensions.

Usage (interactive):
    vic20_host.py [--scale 3] [--fps 60]
    c64_host.py  [--scale 2] [--fps 60]

Usage (headless validation):
    vic20_host.py --frames 300 --preview
    c64_host.py  --frames 300 --dump out.rgba --stats
    c64_host.py  --frames 400 --type 'PRINT"HI"^M' --preview
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# wasmtime bootstrap (mirrors bin/run_wasi.py / reinette apple2_host.py)
# ---------------------------------------------------------------------------


def _bootstrap() -> None:
    """Add a site-packages dir containing wasmtime/pygame to sys.path."""
    # 1) the dedicated hosts venv
    venv_lib = Path("/home/jjs/Projects/atari800/yahtzee-a8/venv/hosts/venv-flat-line/lib")
    if venv_lib.is_dir():
        for sp in venv_lib.glob("python*/site-packages"):
            if str(sp) not in sys.path:
                sys.path.insert(0, str(sp))
    # 2) local .runtime/site-packages (pip --target bootstrap)
    runtime_sp = Path(__file__).resolve().parent / ".runtime" / "site-packages"
    if runtime_sp.is_dir() and str(runtime_sp) not in sys.path:
        sys.path.insert(0, str(runtime_sp))


_bootstrap()

import wasmtime  # noqa: E402

# ---------------------------------------------------------------------------
# Commodore key codes — keep in sync with keymaps.h
# ---------------------------------------------------------------------------

CBM_KEY_DEL = 0x01
CBM_KEY_CTRL = 0x0E
CBM_KEY_CBM = 0x0F      # C= key (C64 only)
CBM_KEY_STOP = 0x03     # RUN/STOP
CBM_KEY_RETURN = 0x0D
CBM_KEY_CSRLEFT = 0x08  # cursor left / backspace
CBM_KEY_CSRRIGHT = 0x09
CBM_KEY_CSRDOWN = 0x0A
CBM_KEY_CSRUP = 0x0B
CBM_KEY_HOME = 0x0C     # HOME (C64 only)
CBM_KEY_CLR = 0x02      # CLR (shift+home, C64 only)
CBM_KEY_LEFTARROW = 0x04  # left-arrow symbol (C64 only)
CBM_KEY_INST = 0x10     # INST (shift+del, C64 only)
CBM_KEY_RESTORE = 0xFF  # RESTORE
CBM_KEY_F1 = 0xF1
CBM_KEY_F2 = 0xF2
CBM_KEY_F3 = 0xF3
CBM_KEY_F4 = 0xF4
CBM_KEY_F5 = 0xF5
CBM_KEY_F6 = 0xF6
CBM_KEY_F7 = 0xF7
CBM_KEY_F8 = 0xF8


# ---------------------------------------------------------------------------
# Emulator binding
# ---------------------------------------------------------------------------


class Emulator:
    """Thin wrapper around the exported wasi_* functions of a chips WASI module."""

    def __init__(self, wasm_path: str, fb_w: int, fb_h: int) -> None:
        self.FB_W = fb_w
        self.FB_H = fb_h
        self._engine = wasmtime.Engine()
        self._store = wasmtime.Store(self._engine)
        wasi = wasmtime.WasiConfig()
        wasi.inherit_stdout()
        wasi.inherit_stderr()
        self._store.set_wasi(wasi)

        linker = wasmtime.Linker(self._engine)
        linker.define_wasi()
        module = wasmtime.Module.from_file(self._engine, wasm_path)
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
        # text-screen RAM access (debug/validation; optional export)
        self._screen_cols = exp.get("wasi_screen_cols")
        self._screen_rows = exp.get("wasi_screen_rows")
        self._screen_text = exp.get("wasi_screen_text")
        self._insert_disk = exp["wasi_insert_disk"]  # stub (Phase 2)
        self._load_prg = exp.get("wasi_load_prg")
        self._malloc = exp["malloc"]
        self._free = exp["free"]

    @staticmethod
    def _resolve_prg_path(path_str: str) -> Path:
        p = Path(path_str)
        if p.is_absolute():
            return p
        # Walk up from CWD looking for a 'disks' dir containing the file;
        # this handles running from repo root or any subdirectory.
        start = Path.cwd()
        for base in [start] + list(start.parents):
            candidate = base / p
            if candidate.exists():
                return candidate.resolve()
        # Last resort: original relative path
        return p

    def load_prg(self, prg_path: str) -> None:
        """Auto-load a C64 PRG file into emulator RAM.

        Reads a .prg file (2-byte LE load address + payload), allocates
        linear memory in the WASM module via malloc(), copies the entire
        file there, then calls wasi_load_prg() which parses the header and
        writes the payload directly into CPU-visible RAM with mem_write_range().
        """
        if self._load_prg is None:
            raise RuntimeError("wasi_load_prg not exported by this module")
        path = self._resolve_prg_path(prg_path)
        data = path.read_bytes()
        ptr = self._malloc(self._store, len(data))
        try:
            self._memory.write(self._store, data, ptr)
            res = self._load_prg(self._store, ptr, len(data))
            if res != 0:
                raise RuntimeError(f"wasi_load_prg failed with code {res}")
        finally:
            self._free(self._store, ptr)

    # -- lifecycle ----------------------------------------------------------
    def init(self) -> None:
        self._init(self._store)

    def tick(self) -> None:
        self._tick(self._store)

    def run(self, n_frames: int) -> None:
        for _ in range(n_frames):
            self.tick()

    # -- input ---------------------------------------------------------------
    def keydown(self, code: int) -> None:
        self._keydown(self._store, code)

    def keyup(self, code: int) -> None:
        self._keyup(self._store, code)

    def press(self, code: int, frames_down: int = 3, frames_up: int = 2) -> None:
        """Send one key down, let the KERNAL poll the matrix, then release it."""
        self.keydown(code)
        self.run(frames_down)
        self.keyup(code)
        self.run(frames_up)

    # -- video ---------------------------------------------------------------
    def reported_dims(self) -> tuple[int, int]:
        return (self._fb_w(self._store), self._fb_h(self._store))

    def framebuffer(self) -> bytearray:
        ptr = self._fb_ptr(self._store)
        n = self.FB_W * self.FB_H * 4
        return self._memory.read(self._store, ptr, ptr + n)

    def pixel_stats(self, fb: bytearray | None = None) -> tuple[int, int, int]:
        """Return (non_black_pixels, total_pixels, distinct_colors)."""
        if fb is None:
            fb = self.framebuffer()
        total = self.FB_W * self.FB_H
        non_black = 0
        colors: set[int] = set()
        stride = 4
        for i in range(0, len(fb), stride):
            r, g, b, a = fb[i], fb[i + 1], fb[i + 2], fb[i + 3]
            colors.add((r, g, b, a))
            if (r | g | b | a) != 0:
                non_black += 1
        return non_black, total, len(colors)

    def screen_text(self) -> list[str] | None:
        """Return the text screen as a list of lines (or None if not exported)."""
        if self._screen_text is None or self._screen_cols is None or self._screen_rows is None:
            return None
        cols = self._screen_cols(self._store)
        rows = self._screen_rows(self._store)
        n = cols * rows
        buf = self._malloc(self._store, n)
        try:
            self._screen_text(self._store, buf, n)
            data = self._memory.read(self._store, buf, buf + n)
        finally:
            self._free(self._store, buf)
        lines = []
        for r in range(rows):
            lines.append("".join(_decode_screen_code(b) for b in data[r * cols:(r + 1) * cols]))
        return lines


# ---------------------------------------------------------------------------
# Key mapping
# ---------------------------------------------------------------------------


def _build_key_map():
    """Return a dict pygame keycode -> Commodore key code (non-printable)."""
    import pygame  # imported lazily so headless mode does not need a display

    return {
        pygame.K_LCTRL: CBM_KEY_CTRL,
        pygame.K_RCTRL: CBM_KEY_CTRL,
        pygame.K_LALT: CBM_KEY_CBM,      # C= key (C64)
        pygame.K_RALT: CBM_KEY_CBM,
        pygame.K_LMETA: CBM_KEY_CBM,     # Super/Windows key also acts as C=
        pygame.K_RMETA: CBM_KEY_CBM,
        pygame.K_RETURN: CBM_KEY_RETURN,
        pygame.K_KP_ENTER: CBM_KEY_RETURN,
        pygame.K_BACKSPACE: CBM_KEY_CSRLEFT,
        pygame.K_DELETE: CBM_KEY_DEL,
        pygame.K_UP: CBM_KEY_CSRUP,
        pygame.K_DOWN: CBM_KEY_CSRDOWN,
        pygame.K_LEFT: CBM_KEY_CSRLEFT,
        pygame.K_RIGHT: CBM_KEY_CSRRIGHT,
        pygame.K_HOME: CBM_KEY_HOME,
        pygame.K_END: CBM_KEY_CLR,       # shift+home = clear
        pygame.K_INSERT: CBM_KEY_INST,
        pygame.K_SPACE: 0x20,
        pygame.K_ESCAPE: CBM_KEY_STOP,   # RUN/STOP
        pygame.K_BACKQUOTE: CBM_KEY_LEFTARROW,
        pygame.K_F1: CBM_KEY_F1,
        pygame.K_F2: CBM_KEY_F2,
        pygame.K_F3: CBM_KEY_F3,
        pygame.K_F4: CBM_KEY_F4,
        pygame.K_F5: CBM_KEY_F5,
        pygame.K_F6: CBM_KEY_F6,
        pygame.K_F7: CBM_KEY_F7,
        pygame.K_F8: CBM_KEY_F8,
    }


def pygame_key_to_commodore(key: int, key_map: dict, unicode_char: str | None = None) -> int:
    """Map a pygame key event to a Commodore key code, or -1 if unmapped.

    chips' keyboard identifiers are the matrix labels; for letters the unshifted
    identifier is UPPERCASE (65-90) and the shifted one is lowercase (97-122).
    The KERNAL displays the unshifted identifier as an uppercase letter, and the
    shifted identifier as a graphics symbol on the VIC-20 (uppercase/graphics
    charset) or a lowercase letter on the C64.

    pygame reports the actual typed character via event.unicode, so we send the
    INVERTED case: typing 'a' (no shift) sends 65 -> 'A' on screen; typing 'A'
    (shift held) sends 97 -> graphics (VIC-20) / 'a' (C64).  This keeps normal
    typing producing readable letters while still allowing graphics via Shift
    (VIC-20) or C=+letter via ALT (C64).
    """
    code = key_map.get(key)
    if code is not None:
        return code
    if unicode_char is not None and len(unicode_char) == 1:
        o = ord(unicode_char)
        if 0x61 <= o <= 0x7A:   # typed lowercase (no shift) -> unshifted identifier
            return o - 0x20
        if 0x41 <= o <= 0x5A:   # typed uppercase (shift held) -> shifted identifier
            return o + 0x20
        if 0x20 <= o < 0x7F:
            return o
    if 0x20 <= key < 0x7F:
        # fallback (unicode unavailable): default letters to the unshifted id
        if 0x61 <= key <= 0x7A:
            key -= 0x20
        return key
    return -1


def text_to_key_sequence(text: str, key_map: dict | None = None) -> list[int]:
    """Convert a string of text into a list of Commodore key codes.

    Recognised escapes (both real control chars and the literal two-character
    sequences, so it works regardless of shell quoting):
        \\n / \\r   -> RETURN
        \\b        -> cursor left
        \\x03      -> RUN/STOP
        \\x0c      -> HOME
        \\x02      -> CLR
    """
    out: list[int] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt in ("n", "r"):
                out.append(CBM_KEY_RETURN)
                i += 2
                continue
            if nxt == "b":
                out.append(CBM_KEY_CSRLEFT)
                i += 2
                continue
            # unknown escape: emit the backslash literally
        if ch in ("\r", "\n"):
            out.append(CBM_KEY_RETURN)
        elif ch == "\b":
            out.append(CBM_KEY_CSRLEFT)
        elif ch == "\x03":
            out.append(CBM_KEY_STOP)
        elif ch == "\x0c":
            out.append(CBM_KEY_HOME)
        elif ch == "\x02":
            out.append(CBM_KEY_CLR)
        else:
            o = ord(ch)
            if 0x61 <= o <= 0x7A:   # a-z -> A-Z (unshifted identifier, see keymaps.h)
                o -= 0x20
            out.append(o)
        i += 1
    return out


# ---------------------------------------------------------------------------
# Preview / dump helpers (headless validation)
# ---------------------------------------------------------------------------


_PREVIEW_CHARS = " .:-=+*#%@"  # dark -> bright

# Commodore screen-code -> display char (standard charset).
# 0x01-0x1A = A-Z, 0x20-0x3F = printable, 0x41-0x5A = a-z (lowercase mode).
_SCREEN_CODE_CHARS = {0x00: "@", 0x1B: "[", 0x1C: "\u00a3", 0x1D: "]", 0x1E: "^", 0x1F: "<"}
for _i in range(0x01, 0x1B):
    _SCREEN_CODE_CHARS[_i] = chr(ord("A") + _i - 0x01)
for _i in range(0x41, 0x5B):
    _SCREEN_CODE_CHARS[_i] = chr(ord("a") + _i - 0x41)


def _decode_screen_code(b: int) -> str:
    if 0x20 <= b <= 0x3F:
        return chr(b)
    return _SCREEN_CODE_CHARS.get(b, ".")


def render_preview(fb: bytearray, fb_w: int, fb_h: int, cell: int = 4) -> list[str]:
    """Downsample the RGBA framebuffer into a coarse luminance ASCII picture."""
    cols = fb_w // cell
    rows = fb_h // cell
    lines: list[str] = []
    for r in range(rows):
        line: list[str] = []
        for c in range(cols):
            lum_sum = 0.0
            cnt = 0
            for y in range(r * cell, min((r + 1) * cell, fb_h)):
                for x in range(c * cell, min((c + 1) * cell, fb_w)):
                    i = (y * fb_w + x) * 4
                    r_, g_, b_ = fb[i], fb[i + 1], fb[i + 2]
                    lum_sum += 0.299 * r_ + 0.587 * g_ + 0.114 * b_
                    cnt += 1
            avg = lum_sum / max(1, cnt)
            idx = int(avg / 256.0 * (len(_PREVIEW_CHARS) - 1))
            idx = max(0, min(idx, len(_PREVIEW_CHARS) - 1))
            line.append(_PREVIEW_CHARS[idx])
        lines.append("".join(line))
    return lines


# ---------------------------------------------------------------------------
# Interactive pygame renderer
# ---------------------------------------------------------------------------


def _wait_for_basic_ready(emu: Emulator, max_frames: int = 300) -> bool:
    """Poll until the BASIC READY prompt is visible on the text screen."""
    for _ in range(max_frames):
        lines = emu.screen_text()
        if lines and any("READY" in line.upper() for line in lines):
            return True
        emu.run(1)
    return False


def _prepare_emu(emu: Emulator, args: argparse.Namespace) -> None:
    """Wait for READY + auto-load a PRG + type text before the main loop.

    Shared by both the interactive (pygame) and headless drivers so the two
    paths behave identically.
    """
    if args.autoload_prg:
        print(f"[host] waiting for BASIC READY...", file=sys.stderr)
        if not _wait_for_basic_ready(emu):
            print("[host] WARNING: READY not detected within timeout; "
                  "loading anyway.", file=sys.stderr)
        print(f"[host] auto-loading PRG: {args.autoload_prg}", file=sys.stderr)
        emu.load_prg(args.autoload_prg)

    if args.type:
        seq = text_to_key_sequence(args.type)
        print(f"[host] typing {len(seq)} keys: {args.type!r} "
              f"(key-frames={args.key_frames})", file=sys.stderr)
        frames_down = max(1, args.key_frames)
        frames_up = max(1, frames_down // 2)
        for code in seq:
            emu.press(code, frames_down=frames_down, frames_up=frames_up)


def run_pygame(emu: Emulator, args: argparse.Namespace) -> None:
    import pygame

    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass

    scale = max(1, args.scale)
    screen = pygame.display.set_mode((emu.FB_W * scale, emu.FB_H * scale))
    pygame.display.set_caption(f"{args.title} (chips WASI)")
    clock = pygame.time.Clock()
    key_map = _build_key_map()
    pressed: dict[int, int] = {}   # pygame keycode -> commodore code (for KEYUP)

    # Autoload + typed input happen inside the interactive session too, so
    # e.g. --autoload-prg FILE --type 'RUN\r' boots, loads, and starts the
    # program in the window instead of silently running headless.
    _prepare_emu(emu, args)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                # Quit is Ctrl+Shift+Q (deliberate) so that plain Ctrl+Q is
                # passed to the emulator like any other Ctrl+letter.
                if (event.key == pygame.K_q
                        and (event.mod & pygame.KMOD_CTRL)
                        and (event.mod & pygame.KMOD_SHIFT)):
                    running = False
                else:
                    code = pygame_key_to_commodore(
                        event.key, key_map, getattr(event, "unicode", None))
                    if code >= 0:
                        pressed[event.key] = code
                        emu.keydown(code)
            elif event.type == pygame.KEYUP:
                code = pressed.pop(event.key, None)
                if code is not None:
                    emu.keyup(code)

        emu.tick()

        fb = emu.framebuffer()
        surface = pygame.image.frombuffer(fb, (emu.FB_W, emu.FB_H), "RGBA")
        scaled = pygame.transform.scale(surface, (emu.FB_W * scale, emu.FB_H * scale))
        screen.blit(scaled, (0, 0))
        pygame.display.flip()
        clock.tick(args.fps)

    pygame.quit()


# ---------------------------------------------------------------------------
# Headless driver
# ---------------------------------------------------------------------------


def run_headless(emu: Emulator, args: argparse.Namespace) -> None:
    """Run a fixed number of frames (optionally typing text) and report."""
    n_pre = args.pre_frames or 60      # let the machine boot before typing
    n_post = args.post_frames or 60    # frames after the last keystroke

    emu.run(n_pre)

    _prepare_emu(emu, args)

    emu.run(n_post)

    fb = emu.framebuffer()
    non_black, total, ncolors = emu.pixel_stats(fb)
    print(f"[headless] reported dims {emu.reported_dims()} (host {emu.FB_W}x{emu.FB_H}); "
          f"pixels non-black {non_black}/{total} ({100.0 * non_black / total:.1f}%); "
          f"distinct colors {ncolors}")

    if args.dump:
        Path(args.dump).write_bytes(fb)
        print(f"[headless] wrote {args.dump} ({len(fb)} bytes)", file=sys.stderr)

    if args.dump_text:
        lines = emu.screen_text()
        if lines is None:
            print("[headless] text-screen export not available in this module", file=sys.stderr)
        else:
            print("== text screen ==")
            for line in lines:
                print(f"  |{line.rstrip()}|")

    if args.preview:
        for line in render_preview(fb, emu.FB_W, emu.FB_H, args.preview_cell):
            print(line)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser(defaults: dict) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Commodore (VIC-20/C64) chips WASI host.")
    parser.add_argument("--wasm", default=defaults["wasm"], help="WASI module path")
    parser.add_argument("--fbw", type=int, default=defaults["fbw"], help="framebuffer width")
    parser.add_argument("--fbh", type=int, default=defaults["fbh"], help="framebuffer height")
    parser.add_argument("--title", default=defaults.get("title", "Commodore"))
    parser.add_argument("--scale", type=int, default=defaults.get("scale", 3), help="pygame scale")

    # headless / validation options
    parser.add_argument("--headless", action="store_true", help="run without a display")
    parser.add_argument("--frames", type=int, default=0, help="total frames in headless mode (0 = auto)")
    parser.add_argument("--pre-frames", type=int, default=60, help="frames before typing")
    parser.add_argument("--post-frames", type=int, default=60, help="frames after typing")
    parser.add_argument("--key-frames", type=int, default=8,
                        help="frames to hold each typed key (prevents keyboard-buffer overflow)")
    parser.add_argument("--type", default="", help="text to type (\\r = RETURN)")
    parser.add_argument("--dump", default="", metavar="FILE.rgba", help="write raw RGBA framebuffer")
    parser.add_argument("--dump-text", action="store_true", help="print decoded text screen")
    parser.add_argument("--preview", action="store_true", help="print ASCII preview")
    parser.add_argument("--preview-cell", type=int, default=4, help="preview cell size in px")
    parser.add_argument("--fps", type=int, default=60, help="pygame frame rate")
    parser.add_argument("--autoload-prg", default="", metavar="FILE.prg",
                        help="auto-load a C64 PRG file into RAM after boot")
    return parser


def main(argv: list[str] | None = None) -> int:
    # default values are overridden by the thin wrapper scripts
    defaults = {
        "wasm": "vic20.wasm",
        "fbw": 232,
        "fbh": 272,
        "title": "Commodore",
        "scale": 3,
    }
    parser = build_parser(defaults)
    args = parser.parse_args(argv)

    emu = Emulator(args.wasm, args.fbw, args.fbh)
    emu.init()

    if args.headless:
        run_headless(emu, args)
        return 0

    try:
        import pygame  # noqa: F401
    except ImportError:
        print("pygame not available and no headless option given; running 120 frames headless.",
              file=sys.stderr)
        args.pre_frames = 0
        args.post_frames = 120
        run_headless(emu, args)
        return 0

    run_pygame(emu, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
