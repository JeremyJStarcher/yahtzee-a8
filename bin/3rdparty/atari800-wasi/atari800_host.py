#!/usr/bin/env python3
"""atari800_host.py — Python host for the Atari800 WASI module.

Loads atari800.wasm with wasmtime, drives the emulator at ~50 Hz (PAL) or
~60 Hz (NTSC), reads the RGBA32 framebuffer from WASM linear memory and
displays it with pygame.  The XL/XE OS and BASIC ROMs are exposed through a
WASI preopened directory: guest path /roms maps to Distribution/Rom.

Usage (interactive):
    atari800_host.py [--scale 2] [--ntsc]
    atari800_host.py --roms /path/to/Rom

Usage (headless validation, no window):
    atari800_host.py --headless --frames 200 --preview
    atari800_host.py --headless --pre-frames 150 --type 'PRINT 3+4' \\
                     --post-frames 30 --dump out.rgba --stats
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# wasmtime bootstrap (mirrors chips-wasi / reinette apple2_host.py)
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

# pygame keycodes used for special keys (SDL1/pygame style; matches the C glue).
K_RETURN = 13
K_BACKSPACE = 8


def _find_roms_dir() -> Path | None:
    """Locate the Distribution/Rom directory relative to this script."""
    here = Path(__file__).resolve().parent
    for cand in (
        here / ".." / "Atari800Win-PLus" / "Distribution" / "Rom",
        here / ".." / ".." / "Atari800Win-PLus" / "Distribution" / "Rom",
    ):
        if (cand / "ATARIXL.ROM").is_file():
            return cand.resolve()
    return None


# ---------------------------------------------------------------------------
# Emulator binding
# ---------------------------------------------------------------------------


class Emulator:
    """Thin wrapper around the exported wasi_* functions of atari800.wasm."""

    def __init__(self, wasm_path: str, roms_dir: Path | None) -> None:
        self._engine = wasmtime.Engine()
        self._store = wasmtime.Store(self._engine)
        wasi = wasmtime.WasiConfig()
        wasi.inherit_stdout()
        wasi.inherit_stderr()
        if roms_dir is not None and roms_dir.is_dir():
            wasi.preopen_dir(str(roms_dir), "/roms")
            print(f"atari800_host: preopened /roms -> {roms_dir}", file=sys.stderr)
        else:
            print("atari800_host: ROM dir not found - booting with built-in EmuOS", file=sys.stderr)
        self._store.set_wasi(wasi)

        linker = wasmtime.Linker(self._engine)
        linker.define_wasi()
        module = wasmtime.Module.from_file(self._engine, wasm_path)
        instance = linker.instantiate(self._store, module)
        exp = instance.exports(self._store)

        self._memory = exp["memory"]
        self._init = exp["wasi_init"]
        self._tick = exp["wasi_tick"]
        self._kd = exp["wasi_keydown"]
        self._ku = exp["wasi_keyup"]
        self._fb = exp["wasi_fb_ptr"]
        self._fb_w = exp["wasi_fb_width"]
        self._fb_h = exp["wasi_fb_height"]
        self._screen_cols = exp.get("wasi_screen_cols")
        self._screen_rows = exp.get("wasi_screen_rows")
        self._screen_text = exp.get("wasi_screen_text")
        self._malloc = exp["malloc"]
        self._free = exp["free"]

    # -- lifecycle ----------------------------------------------------------
    def init(self) -> None:
        self._init(self._store)

    def tick(self) -> None:
        self._tick(self._store)

    def run(self, n_frames: int) -> None:
        for _ in range(n_frames):
            self.tick()

    # -- input ---------------------------------------------------------------
    def keydown(self, pg_key: int, unicode_char: int) -> None:
        self._kd(self._store, pg_key, unicode_char)

    def keyup(self, pg_key: int, unicode_char: int) -> None:
        self._ku(self._store, pg_key, unicode_char)

    def press(self, pg_key: int, unicode_char: int, frames_down: int = 6, frames_up: int = 3) -> None:
        """Send one key down, let the OS poll the keyboard, then release it."""
        self.keydown(pg_key, unicode_char)
        self.run(frames_down)
        self.keyup(pg_key, unicode_char)
        self.run(frames_up)

    # -- video ---------------------------------------------------------------
    def dims(self) -> tuple[int, int]:
        return (self._fb_w(self._store), self._fb_h(self._store))

    def framebuffer(self) -> bytearray:
        w, h = self.dims()
        ptr = self._fb(self._store)
        n = w * h * 4
        return self._memory.read(self._store, ptr, ptr + n)

    def pixel_stats(self, fb: bytearray | None = None) -> tuple[int, int, int]:
        """Return (non_black_pixels, total_pixels, distinct_colors)."""
        if fb is None:
            fb = self.framebuffer()
        w, h = self.dims()
        total = w * h
        non_black = 0
        colors: set = set()
        for i in range(0, len(fb), 4):
            r, g, b, a = fb[i], fb[i + 1], fb[i + 2], fb[i + 3]
            colors.add((r, g, b, a))
            if (r | g | b | a) != 0:
                non_black += 1
        return non_black, total, len(colors)

    def screen_text(self) -> list[str] | None:
        """Return the decoded 40x24 text screen as a list of lines."""
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
            lines.append("".join(_decode_atari_char(b) for b in data[r * cols:(r + 1) * cols]))
        return lines


# ---------------------------------------------------------------------------
# Headless typing / preview helpers
# ---------------------------------------------------------------------------


def _decode_atari_char(ic: int) -> str:
    """Decode an Atari screen (internal) code to a display character.

    Internal codes 0x00-0x7F map to ATASCII 0x20-0x9F (internal + 0x20);
    0x20-0x7E are printable ASCII.  Higher values are graphics/inverse.
    """
    if ic < 96:
        a = ic + 0x20
        if 32 <= a <= 126:
            return chr(a)
    return "."


def text_to_key_sequence(text: str) -> list[tuple[int, int]]:
    """Convert text into a list of (pg_key, unicode) pairs for --type.

    Recognised escapes (both real control chars and literal two-char
    sequences, so it works regardless of shell quoting):
        \\n / \\r   -> RETURN
        \\b        -> BACKSPACE
    """
    out: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt in ("n", "r"):
                out.append((K_RETURN, 0))
                i += 2
                continue
            if nxt == "b":
                out.append((K_BACKSPACE, 0))
                i += 2
                continue
        if ch in ("\r", "\n"):
            out.append((K_RETURN, 0))
        elif ch == "\b":
            out.append((K_BACKSPACE, 0))
        else:
            out.append((0, ord(ch)))
        i += 1
    return out


_PREVIEW_CHARS = " .:-=+*#%@"  # dark -> bright


def preview(fb: bytearray, w: int, h: int, sx: int = 4, sy: int = 4) -> str:
    """Render the framebuffer as coarse ASCII luminance art."""
    lines = []
    for y in range(0, h, sy):
        row = []
        for x in range(0, w, sx):
            i = (y * w + x) * 4
            r, g, b = fb[i], fb[i + 1], fb[i + 2]
            lum = (r + g + b) // 3
            row.append(_PREVIEW_CHARS[min(len(_PREVIEW_CHARS) - 1, lum * len(_PREVIEW_CHARS) // 256)])
        lines.append("".join(row))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def run_headless(args, roms_dir: Path | None) -> None:
    emu = Emulator(args.wasm, roms_dir)
    emu.init()
    if args.frames is not None:
        emu.run(args.frames)
    else:
        emu.run(args.pre_frames)
        for pg, uni in text_to_key_sequence(args.type):
            emu.press(pg, uni, frames_down=args.key_frames)
        emu.run(args.post_frames)
    fb = emu.framebuffer()
    w, h = emu.dims()
    if args.dump:
        Path(args.dump).write_bytes(bytes(fb))
        print(f"wrote {args.dump} ({w}x{h} RGBA)")
    if args.stats:
        nb, total, colors = emu.pixel_stats(fb)
        print(f"pixel stats: {nb}/{total} non-black, {colors} colors")
    if args.dump_text:
        txt = emu.screen_text()
        if txt is not None:
            print("[text screen]")
            for line in txt:
                print(line)
        else:
            print("text screen export not available")
    if args.preview:
        print(preview(fb, w, h))


def run_interactive(args, roms_dir: Path | None) -> None:
    import pygame

    pygame.init()
    emu = Emulator(args.wasm, roms_dir)
    emu.init()
    w, h = emu.dims()
    screen = pygame.display.set_mode((w * args.scale, h * args.scale))
    pygame.display.set_caption("Atari800 (WASI)")
    clock = pygame.time.Clock()
    fps = 60 if args.ntsc else 50
    held: dict[int, int] = {}
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                uni = ev.unicode or ""
                u = ord(uni) if len(uni) == 1 else 0
                emu.keydown(ev.key, u)
                held[ev.key] = u
            elif ev.type == pygame.KEYUP:
                u = held.pop(ev.key, 0)
                emu.keyup(ev.key, u)
        emu.tick()
        fb = emu.framebuffer()
        surf = pygame.image.frombuffer(fb, (w, h), "RGBA")
        scaled = pygame.transform.scale(surf, (w * args.scale, h * args.scale))
        screen.blit(scaled, (0, 0))
        pygame.display.flip()
        clock.tick(fps)
    pygame.quit()


def main() -> None:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Atari800 WASI host (wasmtime + pygame)")
    ap.add_argument("--wasm", default=str(here / "atari800.wasm"))
    ap.add_argument("--roms", default=None, help="host dir mapped to guest /roms")
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--ntsc", action="store_true", help="NTSC @ 60 Hz (default PAL @ 50 Hz)")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--frames", type=int, default=None, help="headless: run exactly N frames")
    ap.add_argument("--pre-frames", type=int, default=150)
    ap.add_argument("--post-frames", type=int, default=40)
    ap.add_argument("--type", default="", help="text to type (\\n = RETURN, \\b = BACKSPACE)")
    ap.add_argument("--key-frames", type=int, default=8, help="frames each key is held")
    ap.add_argument("--dump", default=None, help="write RGBA framebuffer to file")
    ap.add_argument("--dump-text", action="store_true", help="print the decoded 40x24 text screen")
    ap.add_argument("--preview", action="store_true", help="print ASCII luminance preview")
    ap.add_argument("--stats", action="store_true", help="print pixel statistics")
    args = ap.parse_args()

    roms_dir = Path(args.roms).resolve() if args.roms else _find_roms_dir()

    if args.headless:
        run_headless(args, roms_dir)
    else:
        run_interactive(args, roms_dir)


if __name__ == "__main__":
    main()
