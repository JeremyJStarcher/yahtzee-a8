#!/usr/bin/env python3
"""
Font Parser Module

Parses YAFF (Yet Another Font Format) files into usable bitmap data
for the video display component.
"""

import os


class FontParser:
    """Parses .yaff font files and provides glyph lookup."""

    def __init__(self) -> None:
        self._glyphs = {}  # Maps char_index -> list of 8 bytes

    def parse_yaff(self, filepath: str) -> dict[int, bytearray]:
        """
        Parse a YAFF font file.

        Args:
            filepath: Path to the .yaff file

        Returns:
            Dictionary mapping character indices to 8-byte arrays
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Font file not found: {filepath}")

        glyphs = {}
        current_glyph = None

        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n\r")

                # Skip empty lines, comments, and metadata
                if (
                    not line or line.startswith("#") or ":" in line.split()[0]
                    if line
                    else True
                ):
                    # Check if this is a hex index line like "0x00:" or "u+0020:"
                    stripped = line.strip().rstrip(":")
                    if stripped.startswith("0x"):
                        try:
                            current_glyph = int(stripped, 16)
                            continue
                        except ValueError:
                            continue
                    elif stripped.lower().startswith("u+"):
                        # Unicode reference - skip but keep going
                        continue
                    elif ":" in line and not any(c in line for c in [".", "@"]):
                        # Metadata line like "name:", "spacing:", etc.
                        continue
                    else:
                        continue

                # If we have an active glyph and this line contains pixel data
                if current_glyph is not None and line:
                    # Count dots from left to find first @ position
                    bitmap_row = self._parse_bitmap_line(line)
                    if bitmap_row is not None:
                        if current_glyph not in glyphs:
                            glyphs[current_glyph] = []
                        glyphs[current_glyph].append(bitmap_row)

        # Convert lists of bytes to bytearrays
        result = {}
        for idx, rows in glyphs.items():
            if len(rows) == 8:
                result[idx] = bytearray(rows)

        return result

    def _parse_bitmap_line(self, line: str) -> int | None:
        """
        Parse a single bitmap line from yaff format.

        Args:
            line: A line containing '.' and/or '@' characters

        Returns:
            8-bit value representing the row, or None if invalid
        """
        # Remove leading/trailing whitespace
        line = line.strip()

        # Validate it only contains . and @ (and maybe spaces for alignment)
        cleaned = "".join(c for c in line if c in [".", "@"])

        if len(cleaned) != 8:
            return None

        # Convert to byte: @ = 1 (foreground), . = 0 (background)
        bits = 0
        for i, char in enumerate(cleaned):
            if char == "@":
                bits |= 1 << (7 - i)  # MSB first

        return bits


def load_font(filepath: str = "atascii.yaff") -> FontParser:
    """
    Convenience function to load a font file.

    Args:
        filepath: Path to the .yaff file

    Returns:
        FontParser instance with loaded glyphs
    """
    parser = FontParser()
    glyphs = parser.parse_yaff(filepath)
    parser._glyphs = glyphs
    return parser
