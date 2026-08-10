"""
Shared base class for video display implementations.

Provides character/color memory management, offset validation, the common
public API, and a uniform window/event-loop interface.  Rendering backends
(Tk bitmap PhotoImage, native Tk text, or pygame) inherit from this class
and only implement display-specific logic.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import Canvas
from typing import cast

from .font import C64_COLORS, DEFAULT_COLOR, SCREEN_ORDER_CHARS


class BaseVideo:
    """Common video memory, validation, and API shared by all backends."""

    CHARS = SCREEN_ORDER_CHARS
    C64_COLORS = C64_COLORS
    DEFAULT_COLOR = DEFAULT_COLOR

    CHAR_WIDTH: int = 8
    CHAR_HEIGHT: int = 8

    # Keyboard modifier flag bits.  These must stay in sync with the
    # SystemBus definitions in fcon.py (KB_FLAG_SHIFT / KB_FLAG_CTRL) so
    # backends can encode modifier state for the BIOS keyboard registers.
    KB_FLAG_SHIFT = 0x01
    KB_FLAG_CTRL = 0x02

    # Arrow-key constants.  When an arrow key is pressed, the backend
    # sends one of these byte values (with modifier flags) through the
    # normal keyboard pipeline instead of an ASCII code.  The BIOS can
    # read $0200 and compare against these values to detect cursor keys.
    KEY_ARROW_UP = 0x81
    KEY_ARROW_DOWN = 0x82
    KEY_ARROW_LEFT = 0x83
    KEY_ARROW_RIGHT = 0x84

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

        self._key_callback: Callable[[int, int], None] | None = None

        self._root: tk.Tk
        self._canvas: Canvas

    # -- Validation ----------------------------------------------------------

    @staticmethod
    def _validate_dimensions(rows: int, columns: int, scale: int, border: int) -> None:
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
            raise IndexError(f"Offset {offset} out of range [0, {total_cells - 1}]")

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

    # -- Window / event-loop interface ---------------------------------------
    #
    # The emulator drives the display through this small uniform interface
    # rather than reaching into backend-specific widgets.  The default
    # implementations delegate to a Tk root; the pygame backend overrides
    # them with its own window and event loop.

    def _dispatch_key_event(self, ascii_val: int, flags: int) -> None:
        """Dispatch a key event to the registered callback."""
        if self._key_callback:
            self._key_callback(ascii_val, flags)

    def _handle_key_event(self, event: tk.Event) -> None:
        """Decode a Tk key press and forward it to the key callback.

        Extracts Shift/Ctrl modifier flags from ``event.state`` and the
        ASCII value from ``event.char``, then dispatches via
        :meth:`_dispatch_key_event`.  Control characters (BS 0x08,
        TAB 0x09, ESC 0x1B, DEL 0x7F, etc.) are forwarded so they reach
        the BIOS keyboard handler.
        """
        # The tkinter type stub types ``Event.state`` as ``str``, but at
        # runtime it is an int bitmask of modifier keys.
        state = cast(int, event.state)
        flags = 0
        if state & 0x0001:  # Shift mask
            flags |= BaseVideo.KB_FLAG_SHIFT
        if state & 0x0004:  # Control mask
            flags |= BaseVideo.KB_FLAG_CTRL

        ascii_val = ord(event.char) if event.char else 0x00
        if ascii_val != 0x00:
            self._dispatch_key_event(ascii_val, flags)
            return

        # Arrow keys produce no ASCII character but are still useful to
        # the BIOS.  Map them to the dedicated arrow-key constants.
        arrow_map: dict[str, int] = {
            "Up": BaseVideo.KEY_ARROW_UP,
            "Down": BaseVideo.KEY_ARROW_DOWN,
            "Left": BaseVideo.KEY_ARROW_LEFT,
            "Right": BaseVideo.KEY_ARROW_RIGHT,
        }
        arrow_val = arrow_map.get(event.keysym)
        if arrow_val is not None:
            self._dispatch_key_event(arrow_val, flags)

    def set_title(self, title: str) -> None:
        """Set the window title."""
        self._root.title(title)

    def set_close_handler(self, callback: Callable[[], None]) -> None:
        """Register *callback* to run when the user closes the window."""
        self._root.protocol("WM_DELETE_WINDOW", callback)

    def set_key_callback(self, callback: Callable[[int, int], None] | None) -> None:
        """Register *callback* for keyboard events.

        The callback receives ``(ascii_value, flags)`` where *flags*
        encodes modifier state (bit 0 = Shift, bit 1 = Control).
        """
        self._key_callback = callback

    def schedule(self, delay_ms: int, callback: Callable[[], None]) -> None:
        """Run *callback* after *delay_ms* milliseconds on the UI thread."""
        self._root.after(delay_ms, callback)

    def mainloop(self) -> None:
        """Run the window's main event loop until the window is closed."""
        self._root.mainloop()

    def pump(self) -> None:
        """Process pending window events without blocking.

        The default implementation pumps the Tk event queue (which also
        fires any due ``after`` callbacks).  The pygame backend overrides
        this with its own event-loop driver.
        """
        self._root.update()

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
