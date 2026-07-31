"""
Shared base class for video display implementations.

Provides character/color memory management, offset validation, and the
common public API.  Rendering backends (bitmap PhotoImage or native Tk text)
inherit from this class and only implement display-specific logic.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import Canvas

from .font import C64_COLORS, DEFAULT_COLOR, SCREEN_ORDER_CHARS


class BaseVideo:
    """Common video memory, validation, and API shared by all backends."""

    CHARS = SCREEN_ORDER_CHARS
    C64_COLORS = C64_COLORS
    DEFAULT_COLOR = DEFAULT_COLOR

    CHAR_WIDTH: int = 8
    CHAR_HEIGHT: int = 8

    def __init__(
        self, rows: int, columns: int, scale: int = 1, border: int = 1
    ) -> None:
        self._validate_dimensions(rows, columns, scale, border)

        self._rows = rows
        self._columns = columns
        self._scale = scale
        self._border = border

        total_cells = rows * columns
        self._screen_memory = bytearray([0x20] * total_cells)
        self._color_memory = bytearray([self.DEFAULT_COLOR] * total_cells)
        self._dirty = True

        self._root: tk.Tk
        self._canvas: Canvas

    # -- Validation ----------------------------------------------------------

    @staticmethod
    def _validate_dimensions(
        rows: int, columns: int, scale: int, border: int
    ) -> None:
        """Validate constructor parameters."""
        if not isinstance(rows, int) or not isinstance(columns, int):
            raise TypeError("Rows and columns must be integers")
        if rows <= 0 or columns <= 0:
            raise ValueError("Rows and columns must be positive integers")
        if not isinstance(scale, int) or scale < 1:
            raise ValueError("Scale must be a positive integer >= 1")
        if not isinstance(border, int) or border < 0:
            raise ValueError("Border must be a non-negative integer")

    def _validate_offset(self, offset: int) -> None:
        """Raise if *offset* is outside the valid cell range."""
        if not isinstance(offset, int):
            raise TypeError("Offset must be an integer")
        total_cells = self._rows * self._columns
        if offset < 0 or offset >= total_cells:
            raise IndexError(
                f"Offset {offset} out of range [0, {total_cells - 1}]"
            )

    # -- Dirty tracking hook (subclasses may override) -----------------------

    def _mark_cell_dirty(self, offset: int) -> None:
        """Called when a cell's content or color changes.

        The default implementation sets a global dirty flag.  Subclasses
        that track per-cell dirtiness (e.g. for sparse redraws) should
        override this method and then delegate to ``super()``.
        """
        self._dirty = True

    # -- Screen / color memory -----------------------------------------------

    def set_screen(self, offset: int, character: int) -> None:
        """Set a character byte in screen memory."""
        self._validate_offset(offset)
        char_byte = character & 0xFF
        if self._screen_memory[offset] != char_byte:
            self._screen_memory[offset] = char_byte
            self._mark_cell_dirty(offset)

    def get_screen(self, offset: int) -> int:
        """Get the character byte at *offset* in screen memory."""
        self._validate_offset(offset)
        return self._screen_memory[offset]

    def set_color(self, offset: int, color: int) -> None:
        """Set a color byte in color memory.

        Bits 7-4 are the background index; bits 3-0 are the foreground index.
        """
        self._validate_offset(offset)
        color_byte = color & 0xFF
        if self._color_memory[offset] != color_byte:
            self._color_memory[offset] = color_byte
            self._mark_cell_dirty(offset)

    def get_color(self, offset: int) -> int:
        """Get the color byte at *offset* in color memory."""
        self._validate_offset(offset)
        return self._color_memory[offset]

    # -- Scaling -------------------------------------------------------------

    @property
    def scale(self) -> int:
        """Current scaling factor."""
        return self._scale

    # -- Character display ---------------------------------------------------

    def _get_char_display(self, char_byte: int) -> str:
        """Convert a character byte to its displayable Unicode string.

        Uses the ``CHARS`` table to map byte values to characters.
        Returns ``"?"`` for out-of-range indices.
        """
        if char_byte < len(self.CHARS):
            return self.CHARS[char_byte]
        return "?"

    # -- Screencode lookup ---------------------------------------------------

    def get_screencode(self, ch: str) -> int:
        """Return the first screen code corresponding to a Unicode character."""
        if not isinstance(ch, str) or len(ch) != 1:
            raise ValueError("ch must be exactly one Unicode character")
        try:
            return self.CHARS.index(ch)
        except ValueError as error:
            raise ValueError(
                f"Character is not in the screen-code table: {ch!r}"
            ) from error

    # -- Abstract refresh ----------------------------------------------------

    def refresh_screen(self) -> None:
        """Redraw the display.  Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement refresh_screen")

    # -- Cleanup -------------------------------------------------------------

    def close(self) -> None:
        """Destroy the Tk window and release resources."""
        if hasattr(self, "_root") and self._root is not None:
            try:
                self._root.destroy()
            except Exception:
                pass
