"""
Screen dump utilities for the fconsole emulator.

Two dump modes, both driven by the ``FORCE_SCREEN_DUMP`` magic memory
location ($0205):

- Mode 1 (graphics): render the video character and color RAM into an
  8-bit RGB PNG image.  Glyph bitmaps come from the embedded
  ``FONT_DATA`` table (indexed by screen code, bit 0 of each row byte
  is the leftmost pixel -- same convention as the pygame backend) and
  colors come from the C64-compatible palette.

- Mode 2 (text): translate each video character cell into the Unicode
  character it represents using the precomputed ``SCREEN_ORDER_CHARS``
  table (the same table the ``text`` video backend uses to render
  cells) and lay the result out as a plain-text grid, one cell per
  character.

The PNG writer is a small stdlib-only implementation (``struct`` +
``zlib`` + CRC-32) so the headless test path has no third-party image
dependency.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from .font import C64_COLORS, FONT_DATA, SCREEN_ORDER_CHARS

# PNG constants
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_IHDR = b"IHDR"
_PNG_IDAT = b"IDAT"
_PNG_IEND = b"IEND"
_COLOR_TYPE_TRUECOLOR = 2  # 8-bit RGB, no alpha
_BIT_DEPTH_8 = 8
_COMPRESSION_NONE = 0
_FILTER_NONE = 0
_INTERLACE_NONE = 0


def _crc32(data: bytes) -> int:
    """Return the unsigned CRC-32 of *data*."""
    return zlib.crc32(data) & 0xFFFFFFFF


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    """Encode one PNG chunk: length, type, payload, CRC-32."""
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", _crc32(chunk_type + payload))
    )


def _build_font_glyphs() -> dict[int, bytes]:
    """Map screen code -> 8x8 glyph rows (8 bytes per glyph, top row
    first, bit 0 = leftmost pixel)."""
    return {fc.screen_order: bytes(fc.layout) for fc in FONT_DATA}


def screen_to_png(
    char_ram: bytes,
    color_ram: bytes,
    cols: int,
    rows: int,
    cell_width: int = 8,
    cell_height: int = 8,
) -> bytes:
    """Render video RAM into an 8-bit RGB PNG image.

    Args:
        char_ram: screen_size bytes of video character RAM.
        color_ram: screen_size bytes of video color RAM; the high nibble
            is the background color index and the low nibble the
            foreground color index.
        cols: number of character columns on screen.
        rows: number of character rows on screen.
        cell_width: pixel width of one character cell (default 8).
        cell_height: pixel height of one character cell (default 8).

    Returns:
        The complete PNG file content as bytes.

    Raises:
        ValueError: if the RAM buffers do not hold exactly ``cols *
            rows`` cells or are not of equal length.
    """
    cells = cols * rows
    if len(char_ram) < cells or len(color_ram) < cells:
        raise ValueError(
            f"char_ram ({len(char_ram)}) and color_ram ({len(color_ram)}) "
            f"must each hold at least {cells} cells ({cols}x{rows})"
        )

    glyphs = _build_font_glyphs()
    image_width = cols * cell_width
    image_height = rows * cell_height

    row_stride = image_width * 3
    pixel_rows = rows * cell_height
    raw = bytearray()
    for row in range(rows):
        base = row * cols
        # Pre-decode this screen row's cells once; each character cell
        # contributes cell_height consecutive PNG scanlines.
        row_cells: list[tuple[bytes, tuple[int, int, int], tuple[int, int, int]]] = []
        for col in range(cols):
            offset = base + col
            char_code = char_ram[offset]
            color_byte = color_ram[offset]
            row_cells.append(
                (
                    glyphs.get(char_code, b"\x00" * cell_height),
                    C64_COLORS[(color_byte >> 4) & 0x0F],
                    C64_COLORS[color_byte & 0x0F],
                )
            )
        for gy in range(cell_height):
            raw.append(_FILTER_NONE)  # per-scanline filter byte
            for glyph, bg, fg in row_cells:
                glyph_byte = glyph[gy] if gy < len(glyph) else 0
                for gx in range(cell_width):
                    # Bit 0 of the glyph row is the leftmost pixel.
                    pixel = fg if (glyph_byte >> gx) & 1 else bg
                    raw += bytes(pixel)
    expected_raw = pixel_rows * (1 + row_stride)
    if len(raw) != expected_raw:
        raise RuntimeError(
            f"PNG scanline buffer size mismatch: {len(raw)} != {expected_raw}"
        )

    ihdr = struct.pack(
        ">IIBBBBB",
        image_width,
        image_height,
        _BIT_DEPTH_8,
        _COLOR_TYPE_TRUECOLOR,
        _COMPRESSION_NONE,
        _FILTER_NONE,
        _INTERLACE_NONE,
    )
    return (
        _PNG_SIGNATURE
        + _png_chunk(_PNG_IHDR, ihdr)
        + _png_chunk(_PNG_IDAT, zlib.compress(bytes(raw), 9))
        + _png_chunk(_PNG_IEND, b"")
    )


def _cell_char(screen_code: int) -> str:
    """Map one screen code to a printable character for the text dump.

    Uses the ``SCREEN_ORDER_CHARS`` table (same lookup the text video
    backend uses to render cells).  Unmapped slots and control
    characters (e.g. the font's DEL glyph) render as spaces because
    they are not visible on the real display; this also guarantees the
    dump stays a fixed ``cols``-wide grid.
    """
    if screen_code >= len(SCREEN_ORDER_CHARS):
        return " "
    ch = SCREEN_ORDER_CHARS[screen_code]
    if not ch or not ch.isprintable():
        return " "
    return ch


def screen_to_text(char_ram: bytes, cols: int, rows: int) -> str:
    """Translate video character RAM into a plain-text grid.

    Each cell's screen code is mapped through ``SCREEN_ORDER_CHARS``
    (the same lookup the text video backend uses), so both ASCII and
    graphics (box-drawing, etc.) cells round-trip to their visible
    Unicode form.  Colors are intentionally ignored.

    Args:
        char_ram: screen_size bytes of video character RAM.
        cols: number of character columns on screen.
        rows: number of character rows on screen.

    Returns:
        A string of exactly ``rows`` lines, each ``cols`` characters
        long (unmapped or control cells become spaces).

    Raises:
        ValueError: if *char_ram* does not hold ``cols * rows`` cells.
    """
    cells = cols * rows
    if len(char_ram) < cells:
        raise ValueError(
            f"char_ram ({len(char_ram)}) must hold at least {cells} "
            f"cells ({cols}x{rows})"
        )

    lines: list[str] = []
    for row in range(rows):
        base = row * cols
        lines.append("".join(_cell_char(char_ram[base + col]) for col in range(cols)))
    return "\n".join(lines)


def write_dump(
    data: bytes | str, directory: str | Path, mode: int, counter: int
) -> Path:
    """Write a screen dump into *directory* and return the file path.

    Args:
        data: PNG bytes (mode 1) or text (mode 2).
        directory: target directory, created if missing.
        mode: 1 for image dumps, 2 for text dumps.
        counter: 1-based sequence number embedded in the filename.

    Returns:
        The full path of the written file.

    Raises:
        ValueError: for an unsupported *mode*.
    """
    if mode not in (1, 2):
        raise ValueError(f"unsupported screen dump mode: {mode}")

    suffix = ".png" if mode == 1 else ".txt"
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"dump_{counter:04d}{suffix}"
    if mode == 1:
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("mode 1 (image) dump data must be bytes")
        path.write_bytes(bytes(data))
    else:
        if not isinstance(data, str):
            raise TypeError("mode 2 (text) dump data must be str")
        path.write_text(data + "\n", encoding="utf-8")
    return path
