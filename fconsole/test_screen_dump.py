#!/usr/bin/env python3
"""Tests for the screen dump feature (FORCE_SCREEN_DUMP at $0205).

Covers:
- pylib.screen_dump.screen_to_text: screen-code -> text translation using
  the existing SCREEN_ORDER_CHARS table (ASCII and graphics cells), exact
  grid dimensions, error handling.
- pylib.screen_dump.screen_to_png: valid PNG structure (signature, IHDR
  dimensions, IDAT/IEND chunks, CRCs), decoded pixel spot-checks
  (foreground/background colors, glyph bit 0 = leftmost pixel), error
  handling.
- SystemBus FORCE_SCREEN_DUMP register semantics: writes of 1/2 trigger
  the dump callback exactly once, the register self-clears to 0, other
  values latch without triggering, and reads reflect the latched value.
- End-to-end headless boot: a real BIOS under ``fcon.py --headless`` with
  the BIOS-gated self-test armed fills row 3 with a known message and both
  dump file types land on disk with correct content/structure.  The BIOS
  is rebuilt via ../build.py bios first if it is stale relative to its
  sources.

Run from the fconsole/ directory:  python3 test_screen_dump.py
"""

from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
import traceback
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fcon import EmulatorConfig, SystemBus
from pylib import screen_dump
from pylib.font import C64_COLORS, FONT_DATA, SCREEN_ORDER_CHARS

COLS = 40
ROWS = 24
CELLS = COLS * ROWS

# Screen code for the space glyph (the font scrambles screen order, so the
# space is not 0x20 -- it is DEFAULT_SCREEN_CHAR = 181 in hw_limits.inc).
SPACE_SC = 181
assert SCREEN_ORDER_CHARS[SPACE_SC] == " "

FCON_DIR = Path(__file__).resolve().parent
_REPO_ROOT = FCON_DIR.parent
_BIOS_BIN = FCON_DIR / "bios" / "bios.bin"
_BIOS_SOURCES = [
    FCON_DIR / "bios" / "src" / name
    for name in (
        "bios.asm",
        "vectors.asm",
        "branches.inc",
        "math.inc",
        "hw_limits.inc",
        "timer.mac",
    )
]


def _screen_code_for(ch: str) -> int:
    """Return the screen code for a Unicode character (via FONT_DATA)."""
    for sc in range(len(SCREEN_ORDER_CHARS)):
        if SCREEN_ORDER_CHARS[sc] == ch:
            return sc
    raise ValueError(f"no screen code for {ch!r}")


def _default_config() -> EmulatorConfig:
    return EmulatorConfig(
        screen_cols=COLS,
        screen_rows=ROWS,
        screen_scale=1,
        video_backend="tk",
        text_font_family=None,
        instructions_per_batch=8000,
        clock_hz=3_000_000.0,
        fallback_cycles_per_instruction=3.0,
        max_catch_up_seconds=0.1,
        host_yield_ms=1,
        refresh_interval_ms=16,
        screen_size=CELLS,
        start_region_char_ram=0xA000,
        start_region_color_ram=0xB000,
        headless=True,
        headless_cycles=1_000_000,
        screen_dump_dir="screen_dumps",
    )


# ---------------------------------------------------------------------------
# screen_to_text
# ---------------------------------------------------------------------------


def test_text_dump_ascii() -> None:
    """Row 0 'Hello' + row 1 digits, everything else spaces."""
    char_ram = bytearray([SPACE_SC] * CELLS)  # screen code for the space glyph
    for i, ch in enumerate("Hello"):
        char_ram[i] = _screen_code_for(ch)
    for i, ch in enumerate("12345"):
        char_ram[COLS + i] = _screen_code_for(ch)

    text = screen_dump.screen_to_text(bytes(char_ram), COLS, ROWS)
    lines = text.split("\n")
    assert len(lines) == ROWS, f"expected {ROWS} lines, got {len(lines)}"
    assert all(len(line) == COLS for line in lines), "every line must be 40 chars"
    assert lines[0].startswith("Hello"), f"row 0 = {lines[0]!r}"
    assert lines[1].startswith("12345"), f"row 1 = {lines[1]!r}"
    assert lines[5] == " " * COLS, "blank row 5 must be all spaces"
    print("  ok  test_text_dump_ascii")


def test_text_dump_graphics_glyphs() -> None:
    """Box-drawing cells must map to their box-drawing Unicode codepoints."""
    char_ram = bytearray([SPACE_SC] * CELLS)
    char_ram[0] = _screen_code_for("\u2588")  # full block
    char_ram[1] = _screen_code_for("\u2502")  # vertical line, if present
    text = screen_dump.screen_to_text(bytes(char_ram), COLS, ROWS)
    lines = text.split("\n")
    assert lines[0][0] == "\u2588", f"cell 0 = {lines[0][0]!r}, expected full block"
    assert lines[0][1] == "\u2502", f"cell 1 = {lines[0][1]!r}, expected vertical line"
    print("  ok  test_text_dump_graphics_glyphs")


def test_text_dump_full_scan_roundtrip() -> None:
    """All 256 screen codes in the grid translate per-cell to expected chars."""
    char_ram = bytearray([SPACE_SC] * CELLS)
    char_ram[:256] = bytes(range(256))
    text = screen_dump.screen_to_text(bytes(char_ram), COLS, ROWS)
    lines = text.split("\n")
    for sc in range(256):
        row, col = divmod(sc, COLS)
        expected = SCREEN_ORDER_CHARS[sc]
        if not expected or not expected.isprintable():
            expected = " "
        assert lines[row][col] == expected, (
            f"screen code {sc} at row {row} col {col}: "
            f"got {lines[row][col]!r}, expected {expected!r}"
        )
    # The 256-code sweep fills rows 0..6 (cols 0..15 of row 6); row 7 and
    # beyond must still be all spaces.
    for row in range(7, ROWS):
        assert lines[row] == " " * COLS, f"row {row} should be blank"
    print("  ok  test_text_dump_full_scan_roundtrip")


def test_text_dump_too_small() -> None:
    try:
        screen_dump.screen_to_text(b"\x20" * 10, COLS, ROWS)
    except ValueError:
        print("  ok  test_text_dump_too_small")
        return
    raise AssertionError("expected ValueError for short char_ram")


# ---------------------------------------------------------------------------
# screen_to_png
# ---------------------------------------------------------------------------


def _parse_png(png: bytes) -> tuple[int, int, bytes]:
    """Return (width, height, decompressed raw) for an 8-bit RGB PNG."""
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "missing PNG signature"
    pos = 8
    width = height = 0
    idat = b""
    saw_iend = False
    while pos < len(png):
        (length,) = struct.unpack(">I", png[pos : pos + 4])
        chunk_type = png[pos + 4 : pos + 8]
        payload = png[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack(">I", png[pos + 8 + length : pos + 12 + length])
        assert crc == (zlib.crc32(chunk_type + payload) & 0xFFFFFFFF), (
            f"CRC mismatch in chunk {chunk_type!r}"
        )
        if chunk_type == b"IHDR":
            width, height = struct.unpack(">II", payload[:8])
        elif chunk_type == b"IDAT":
            idat += payload
        elif chunk_type == b"IEND":
            saw_iend = True
            break
        pos += 12 + length
    assert saw_iend, "missing IEND chunk"
    return width, height, zlib.decompress(idat)


def test_png_structure() -> None:
    char_ram = bytes(i % 256 for i in range(CELLS))
    color_ram = bytes([0x6F] * CELLS)
    png = screen_dump.screen_to_png(char_ram, color_ram, COLS, ROWS)
    width, height, raw = _parse_png(png)
    assert width == COLS * 8, f"width {width} != 320"
    assert height == ROWS * 8, f"height {height} != 192"
    expected_raw_len = height * (1 + width * 3)
    assert len(raw) == expected_raw_len, (
        f"raw scanline data {len(raw)} != {expected_raw_len}"
    )
    assert all(raw[y * (1 + width * 3)] == 0 for y in range(height)), (
        "every scanline must use filter type 0"
    )
    print("  ok  test_png_structure")


def test_png_pixel_colors() -> None:
    """Solid block glyph, yellow fg on blue bg: fg/bg pixels correct."""
    char_ram = bytes([_screen_code_for("\u2588")] * CELLS)
    color_ram = bytes([0x67] * CELLS)  # bg=6 (blue), fg=7 (yellow)
    png = screen_dump.screen_to_png(char_ram, color_ram, COLS, ROWS)
    _, _, raw = _parse_png(png)
    stride = COLS * 8 * 3
    # First pixel of pixel row 0 = first foreground pixel of the full block.
    assert raw[1:4] == bytes(C64_COLORS[7]), "first pixel should be fg yellow"
    assert raw[1 + 3 : 4 + 3] == bytes(C64_COLORS[7]), "pixel 1 should be fg"
    # Last pixel row, rightmost pixel: full block -> still fg.
    last_off = 1 + (ROWS * 8 - 1) * (1 + stride) + (stride - 3)
    assert raw[last_off : last_off + 3] == bytes(C64_COLORS[7]), (
        "full block bottom-right pixel should be fg"
    )
    print("  ok  test_png_pixel_colors")


def test_png_background_and_bit_order() -> None:
    """Space cells render background only; the backslash glyph's bit
    pattern proves bit 0 of each glyph row is the leftmost pixel."""
    color_ram = bytes([0x25] * CELLS)  # bg=2 red, fg=5 green
    stride = COLS * 8 * 3

    # A screen of pure spaces must be entirely background.
    char_ram = bytes([SPACE_SC] * CELLS)
    png = screen_dump.screen_to_png(char_ram, color_ram, COLS, ROWS)
    _, _, raw = _parse_png(png)
    assert raw[1:4] == bytes(C64_COLORS[2]), "space cell must render bg only"
    assert raw[1 + stride - 3 : 1 + stride] == bytes(C64_COLORS[2]), (
        "last pixel of the row must render bg"
    )

    # Backslash glyph layout (from FONT_DATA): 60 30 18 0C 06 03 01 00.
    # Row 0 (0x60) sets bits 1..5 -> pixel columns 1..5; row 6 (0x01)
    # sets bit 0 -> pixel column 0; row 7 (0x00) is empty.  This is
    # asymmetric, so a flipped bit order would fail these checks.
    backslash = next(fc for fc in FONT_DATA if fc.codepoint == 0x2F)
    assert bytes(backslash.layout) == bytes(
        [0x60, 0x30, 0x18, 0x0C, 0x06, 0x03, 0x01, 0x00]
    ), "backslash glyph layout changed; update this test"
    backslash_sc = backslash.screen_order

    char_ram = bytearray([SPACE_SC] * CELLS)
    char_ram[0] = backslash_sc
    png = screen_dump.screen_to_png(bytes(char_ram), color_ram, COLS, ROWS)
    _, _, raw = _parse_png(png)

    def cell_pixel(x: int, y: int) -> bytes:
        row_start = 1 + y * (1 + stride)
        return raw[row_start + x * 3 : row_start + x * 3 + 3]

    for gy in range(8):
        glyph_byte = backslash.layout[gy]
        for gx in range(8):
            expected = (
                bytes(C64_COLORS[5]) if (glyph_byte >> gx) & 1 else bytes(C64_COLORS[2])
            )
            got = cell_pixel(gx, gy)
            assert got == expected, (
                f"backslash pixel ({gx},{gy}) = {got!r}, expected {expected!r}"
            )
    # The neighbor cell (1,0) must still be background only.
    for gy in range(8):
        assert cell_pixel(8 + gy, gy) == bytes(C64_COLORS[2]), (
            f"space cell (1,0) pixel ({8 + gy},{gy}) must be bg"
        )
    print("  ok  test_png_background_and_bit_order")


def test_png_too_small() -> None:
    try:
        screen_dump.screen_to_png(b"\x20" * 10, b"\x67" * 10, COLS, ROWS)
    except ValueError:
        print("  ok  test_png_too_small")
        return
    raise AssertionError("expected ValueError for short RAM buffers")


# ---------------------------------------------------------------------------
# write_dump
# ---------------------------------------------------------------------------


def test_write_dump(tmp_dir: Path) -> None:
    png_path = screen_dump.write_dump(b"pngbytes", tmp_dir, 1, 1)
    txt_path = screen_dump.write_dump("hello", tmp_dir, 2, 2)
    assert png_path.name == "dump_0001.png"
    assert txt_path.name == "dump_0002.txt"
    assert png_path.read_bytes() == b"pngbytes"
    assert txt_path.read_text(encoding="utf-8") == "hello\n"
    try:
        screen_dump.write_dump(b"x", tmp_dir, 3, 3)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for bad mode")
    print("  ok  test_write_dump")


# ---------------------------------------------------------------------------
# SystemBus $0205 register semantics
# ---------------------------------------------------------------------------


def test_force_screen_dump_register(tmp_dir: Path) -> None:
    config = _default_config()
    config.screen_dump_dir = str(tmp_dir)
    triggers: list[int] = []
    bus = SystemBus(config, screen_dump_cb=triggers.append)

    # Initial state: 0, no triggers.
    assert bus[SystemBus.FORCE_SCREEN_DUMP] == 0
    assert triggers == []

    # Writing 1 or 2 triggers exactly one dump and self-clears.
    bus[SystemBus.FORCE_SCREEN_DUMP] = 1
    assert triggers == [1], f"write of 1 must trigger mode 1: {triggers}"
    assert bus[SystemBus.FORCE_SCREEN_DUMP] == 0, "register must self-clear"

    bus[SystemBus.FORCE_SCREEN_DUMP] = 2
    assert triggers == [1, 2], f"write of 2 must trigger mode 2: {triggers}"
    assert bus[SystemBus.FORCE_SCREEN_DUMP] == 0

    # Writing 0 or other values latches without triggering.
    bus[SystemBus.FORCE_SCREEN_DUMP] = 0
    assert triggers == [1, 2]
    bus[SystemBus.FORCE_SCREEN_DUMP] = 7
    assert triggers == [1, 2], "other values must not trigger a dump"
    assert bus[SystemBus.FORCE_SCREEN_DUMP] == 7, "other values latch"

    # Re-write 2 after latch: triggers again.
    bus[SystemBus.FORCE_SCREEN_DUMP] = 2
    assert triggers == [1, 2, 2]
    assert bus[SystemBus.FORCE_SCREEN_DUMP] == 0

    # Writes to RAM near the register are unaffected.
    bus[SystemBus.FORCE_SCREEN_DUMP - 1] = 0xAB
    assert bus[SystemBus.FORCE_SCREEN_DUMP - 1] == 0xAB
    print("  ok  test_force_screen_dump_register")


def test_dump_files_written_by_bus(tmp_dir: Path) -> None:
    """End-to-end at the bus level: fill VRAM, write $0205 = 2 and = 1,
    and verify both dump files appear with the right content."""
    config = _default_config()
    config.screen_dump_dir = str(tmp_dir)

    dumps: list[tuple[int, Path]] = []

    def dump_cb(mode: int) -> None:
        bus = cb_bus
        char_ram = bus.read_char_ram()
        color_ram = bus.read_color_ram()
        data: bytes | str
        if mode == 1:
            data = screen_dump.screen_to_png(
                char_ram, color_ram, config.screen_cols, config.screen_rows
            )
        else:
            data = screen_dump.screen_to_text(
                char_ram, config.screen_cols, config.screen_rows
            )
        path = screen_dump.write_dump(
            data, config.screen_dump_dir, mode, len(dumps) + 1
        )
        dumps.append((mode, path))

    cb_bus = SystemBus(config, screen_dump_cb=dump_cb)

    # Write "DUMP TEST" (screen codes) into row 0.
    msg = "DUMP TEST"
    for i, ch in enumerate(msg):
        cb_bus[config.start_region_char_ram + i] = _screen_code_for(ch)

    cb_bus[SystemBus.FORCE_SCREEN_DUMP] = 2
    cb_bus[SystemBus.FORCE_SCREEN_DUMP] = 1

    assert [mode for mode, _ in dumps] == [2, 1]
    txt_path, png_path = dumps[0][1], dumps[1][1]
    assert txt_path.suffix == ".txt" and png_path.suffix == ".png"
    first_line = txt_path.read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith(msg), f"dumped text row 0 = {first_line!r}"
    width, height, _ = _parse_png(png_path.read_bytes())
    assert (width, height) == (COLS * 8, ROWS * 8)
    print("  ok  test_dump_files_written_by_bus")


# ---------------------------------------------------------------------------
# End-to-end headless boot
# ---------------------------------------------------------------------------

_EXPECTED_ROW3_PREFIX = "FCON DUMP TEST OK"
_CYCLE_BUDGET = 3_000_000


def ensure_bios() -> None:
    """Rebuild the BIOS via ../build.py bios when missing or stale."""
    inputs = [p for p in _BIOS_SOURCES if p.is_file()]
    stale = not _BIOS_BIN.is_file() or any(
        src.stat().st_mtime > _BIOS_BIN.stat().st_mtime for src in inputs
    )
    if not stale:
        print(f"  using existing {_BIOS_BIN.name}")
        return
    print("Building BIOS via ../build.py bios ...")
    result = subprocess.run(
        [sys.executable, str(_REPO_ROOT / "build.py"), "bios"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise SystemExit(f"ERROR: BIOS build failed (exit {result.returncode})")


def test_headless_boot_end_to_end() -> None:
    """Real BIOS + real CPU: arm the BIOS self-test, boot headless under
    fcon.py, and verify both dump files land with correct content.

    The BIOS fills row 3 of char RAM with 'FCON DUMP TEST OK' through the
    p2slookup table, writes $0205 = 2 then 1, and freezes; the host ends
    the run at the cycle budget.
    """
    ensure_bios()
    with tempfile.TemporaryDirectory(prefix="fcon_e2e_dump_") as td:
        dump_dir = Path(td)
        cmd = [
            sys.executable,
            str(FCON_DIR / "fcon.py"),
            "--headless",
            "--cycles",
            str(_CYCLE_BUDGET),
            "--screen-dump-selftest",
            "--screen-dump-dir",
            str(dump_dir),
        ]
        print("Running:", " ".join(cmd))
        proc = subprocess.run(
            cmd, cwd=FCON_DIR, capture_output=True, text=True, timeout=180
        )

        assert proc.returncode == 0, (
            f"headless run exited {proc.returncode}\nstdout:\n{proc.stdout}"
            f"\nstderr:\n{proc.stderr}"
        )
        assert "Headless run complete" in proc.stdout, (
            "run did not reach the completion banner"
        )

        txt_files = sorted(dump_dir.glob("dump_*.txt"))
        png_files = sorted(dump_dir.glob("dump_*.png"))
        assert len(txt_files) == 1 and txt_files[0].name == "dump_0001.txt", (
            f"text dumps: {[p.name for p in txt_files]}"
        )
        assert len(png_files) == 1 and png_files[0].name == "dump_0002.png", (
            f"image dumps: {[p.name for p in png_files]}"
        )

        lines = txt_files[0].read_text(encoding="utf-8").splitlines()
        assert len(lines) == ROWS, f"expected {ROWS} lines, got {len(lines)}"
        assert all(len(line) == COLS for line in lines), (
            "every text row must be exactly 40 chars"
        )
        expected_row3 = _EXPECTED_ROW3_PREFIX + " " * (
            COLS - len(_EXPECTED_ROW3_PREFIX)
        )
        assert lines[3] == expected_row3, f"row 3 = {lines[3]!r}"
        assert lines[0].startswith("Welcome"), f"row 0 = {lines[0]!r}"

        width, height, _ = _parse_png(png_files[0].read_bytes())
        assert (width, height) == (COLS * 8, ROWS * 8), (
            f"PNG dimensions {width}x{height}"
        )
    print("  ok  test_headless_boot_end_to_end")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_TMP_TESTS = {
    "test_write_dump",
    "test_force_screen_dump_register",
    "test_dump_files_written_by_bus",
}


def main() -> None:
    passed = 0
    failed = 0
    print("Screen dump tests:")

    with tempfile.TemporaryDirectory(prefix="fcon_dump_test_") as td:
        tmp = Path(td)
        for name, fn in sorted(globals().items()):
            if not name.startswith("test_") or not callable(fn):
                continue
            try:
                if name in _TMP_TESTS:
                    fn(tmp)
                else:
                    fn()
                passed += 1
            except Exception:
                failed += 1
                print(f"  FAIL {name}")
                print(traceback.format_exc())

    if failed:
        print(f"\n{failed} test(s) failed, {passed} passed.")
        sys.exit(1)
    print(f"\nAll {passed} tests passed.")


if __name__ == "__main__":
    main()
