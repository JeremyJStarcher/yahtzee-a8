"""
Native Text Display Component for the 8-bit Computer Emulator

Drop-in alternative to ``pylib.video_display.Video``.  It renders each
character cell with persistent Tk Canvas text and rectangle objects rather
than constructing bitmap PhotoImages.

No third-party Python packages are required.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import Canvas
from tkinter import font as tkfont

from .font import SCREEN_ORDER_CHARS
from .video_base import BaseVideo


class Video(BaseVideo):
    """A native-text video display with character and color memory."""

    # Tk normally cannot display U+007F.  This visible Unicode control-picture
    # substitute keeps screen code $7F inspectable in native-text mode.
    _DISPLAY_SUBSTITUTIONS = {0x7F: "\u2421"}

    _CHAR_TO_CODE: dict[str, int] = {}
    for _index, _character in enumerate(SCREEN_ORDER_CHARS):
        _CHAR_TO_CODE.setdefault(_character, _index)
    del _index, _character

    def __init__(
        self,
        rows: int,
        columns: int,
        scale: int = 1,
        border: int = 1,
        font_family: str | None = None,
    ) -> None:
        super().__init__(rows, columns, scale, border)

        self._requested_font_family = font_family

        # Per-cell dirty tracking (overrides the base class's simple flag)
        self._dirty_cells: set[int] = set(range(len(self._screen_memory)))

        self._root = tk.Tk()
        self._root.title("Native Text Video Display")

        self._canvas = Canvas(self._root, highlightthickness=0, takefocus=True)
        self._canvas.pack()

        self._palette_hex = [
            f"#{red:02x}{green:02x}{blue:02x}"
            for red, green, blue in self.C64_COLORS
        ]

        self._font: tkfont.Font
        self._font_family = ""
        self._cell_width = 0
        self._cell_height = 0
        self._background_items: list[int] = []
        self._text_items: list[int] = []

        self._selection_anchor: int | None = None
        self._selection_end: int | None = None

        self._configure_font_and_geometry()
        self._create_cell_items()
        self._install_bindings()
        self.refresh_screen()
        self._canvas.focus_set()

    # -- Dirty tracking override ---------------------------------------------

    def _mark_cell_dirty(self, offset: int) -> None:
        """Track per-cell dirtiness for sparse redraws."""
        self._dirty_cells.add(offset)
        super()._mark_cell_dirty(offset)

    # -- Scaling -------------------------------------------------------------

    @BaseVideo.scale.setter
    def scale(self, value: int) -> None:
        if not isinstance(value, int) or value < 1:
            raise ValueError("Scale must be a positive integer >= 1")
        if value == self._scale:
            return

        self._scale = value
        self._configure_font_and_geometry()
        self._create_cell_items()
        self._dirty_cells = set(range(len(self._screen_memory)))
        self._dirty = True
        self.refresh_screen()

    # -- Font / geometry properties ------------------------------------------

    @property
    def font_family(self) -> str:
        """Return the actual font family selected by Tk."""
        return self._font_family

    @property
    def cell_width(self) -> int:
        """Measured cell width in pixels for the current font."""
        return self._cell_width

    @property
    def cell_height(self) -> int:
        """Measured cell height in pixels for the current font."""
        return self._cell_height

    def _configure_font_and_geometry(self) -> None:
        base_font = tkfont.nametofont("TkFixedFont")
        family = self._requested_font_family or str(base_font.actual("family"))

        # A negative Tk font size is measured in pixels rather than points.
        # This makes --screen-scale predictable across desktop DPI settings.
        pixel_height = max(8, self.CHAR_HEIGHT * self._scale)
        self._font = tkfont.Font(
            root=self._root,
            family=family,
            size=-pixel_height,
            weight="normal",
            slant="roman",
        )
        self._font_family = str(self._font.actual("family"))

        display_chars = [self._display_character(code) for code in range(256)]
        measured_width = max(
            self._font.measure(character) for character in display_chars
        )
        self._cell_width = max(1, measured_width)
        self._cell_height = max(1, int(self._font.metrics("linespace")))

        width = (self._columns + 2 * self._border) * self._cell_width
        height = (self._rows + 2 * self._border) * self._cell_height

        self._root.title(
            f"Native Text Display ({self._rows}x{self._columns}) "
            f"[{self._font_family}, scale={self._scale}x]"
        )
        self._root.geometry(f"{width}x{height}")
        self._root.resizable(False, False)
        self._canvas.configure(width=width, height=height, bg="black")

    def _create_cell_items(self) -> None:
        self._canvas.delete("all")
        self._background_items.clear()
        self._text_items.clear()

        default_bg, default_fg = self._get_color_hex(self.DEFAULT_COLOR)
        for offset in range(len(self._screen_memory)):
            row, col = divmod(offset, self._columns)
            x1 = (col + self._border) * self._cell_width
            y1 = (row + self._border) * self._cell_height
            x2 = x1 + self._cell_width
            y2 = y1 + self._cell_height

            bg_item = self._canvas.create_rectangle(
                x1, y1, x2, y2, fill=default_bg, outline="",
            )
            text_item = self._canvas.create_text(
                x1 + self._cell_width / 2,
                y1 + self._cell_height / 2,
                text=" ",
                fill=default_fg,
                font=self._font,
                anchor="center",
            )
            self._background_items.append(bg_item)
            self._text_items.append(text_item)

        self._redraw_selection()

    def _install_bindings(self) -> None:
        self._canvas.bind("<Button-1>", self._selection_start)
        self._canvas.bind("<B1-Motion>", self._selection_drag)
        self._canvas.bind("<ButtonRelease-1>", self._selection_finish)
        self._root.bind("<Control-c>", self._copy_selection)
        self._root.bind("<Control-C>", self._copy_selection)
        self._root.bind("<Control-a>", self._select_all)
        self._root.bind("<Control-A>", self._select_all)
        self._root.bind("<Escape>", self._clear_selection)

    # -- Display helpers -----------------------------------------------------

    def _display_character(self, char_byte: int) -> str:
        return self._DISPLAY_SUBSTITUTIONS.get(char_byte, self.CHARS[char_byte])

    def _get_color_hex(self, color_byte: int) -> tuple[str, str]:
        bg_index = (color_byte >> 4) & 0x0F
        fg_index = color_byte & 0x0F
        return self._palette_hex[bg_index], self._palette_hex[fg_index]

    # -- Screencode override (uses pre-built reverse map) --------------------

    def get_screencode(self, ch: str) -> int:
        """Return the first screen code corresponding to a Unicode character."""
        if not isinstance(ch, str) or len(ch) != 1:
            raise ValueError("ch must be exactly one Unicode character")
        try:
            return self._CHAR_TO_CODE[ch]
        except KeyError as error:
            raise ValueError(
                f"Character is not in the screen-code table: {ch!r}"
            ) from error

    # -- Refresh -------------------------------------------------------------

    def refresh_screen(self) -> None:
        """Apply only changed cells to the persistent Canvas objects."""
        if not hasattr(self, "_canvas") or self._canvas is None:
            return

        if self._dirty:
            for offset in tuple(self._dirty_cells):
                bg_hex, fg_hex = self._get_color_hex(self._color_memory[offset])
                self._canvas.itemconfigure(
                    self._background_items[offset], fill=bg_hex
                )
                self._canvas.itemconfigure(
                    self._text_items[offset],
                    text=self._display_character(self._screen_memory[offset]),
                    fill=fg_hex,
                    font=self._font,
                )

            self._dirty_cells.clear()
            self._dirty = False

        try:
            self._root.update_idletasks()
        except tk.TclError:
            pass

    # -- Text export ---------------------------------------------------------

    def get_text(
        self,
        start_offset: int | None = None,
        end_offset: int | None = None,
        *,
        trim_right: bool = True,
    ) -> str:
        """Return the whole screen or a linear cell selection as Unicode text."""
        last_offset = len(self._screen_memory) - 1
        start = 0 if start_offset is None else start_offset
        end = last_offset if end_offset is None else end_offset
        self._validate_offset(start)
        self._validate_offset(end)
        if start > end:
            start, end = end, start

        first_row, first_col = divmod(start, self._columns)
        last_row, last_col = divmod(end, self._columns)
        lines: list[str] = []

        for row in range(first_row, last_row + 1):
            col_start = first_col if row == first_row else 0
            col_end = last_col if row == last_row else self._columns - 1
            row_base = row * self._columns
            line = "".join(
                self._display_character(self._screen_memory[row_base + col])
                for col in range(col_start, col_end + 1)
            )
            lines.append(line.rstrip(" ") if trim_right else line)

        return "\n".join(lines)

    # -- Selection handling --------------------------------------------------

    def _event_to_offset(self, event: tk.Event) -> int | None:
        col = event.x // self._cell_width - self._border
        row = event.y // self._cell_height - self._border
        if row < 0 or row >= self._rows or col < 0 or col >= self._columns:
            return None
        return row * self._columns + col

    def _selection_start(self, event: tk.Event) -> str:
        self._canvas.focus_set()
        offset = self._event_to_offset(event)
        if offset is None:
            self._selection_anchor = None
            self._selection_end = None
        else:
            self._selection_anchor = offset
            self._selection_end = offset
        self._redraw_selection()
        return "break"

    def _selection_drag(self, event: tk.Event) -> str:
        if self._selection_anchor is None:
            return "break"
        offset = self._event_to_offset(event)
        if offset is not None:
            self._selection_end = offset
            self._redraw_selection()
        return "break"

    def _selection_finish(self, event: tk.Event) -> str:
        return self._selection_drag(event)

    def _select_all(self, _event: tk.Event | None = None) -> str:
        self._selection_anchor = 0
        self._selection_end = len(self._screen_memory) - 1
        self._redraw_selection()
        return "break"

    def _clear_selection(self, _event: tk.Event | None = None) -> str:
        self._selection_anchor = None
        self._selection_end = None
        self._redraw_selection()
        return "break"

    def _redraw_selection(self) -> None:
        if not hasattr(self, "_canvas"):
            return
        self._canvas.delete("selection")
        if self._selection_anchor is None or self._selection_end is None:
            return

        start = min(self._selection_anchor, self._selection_end)
        end = max(self._selection_anchor, self._selection_end)
        first_row, first_col = divmod(start, self._columns)
        last_row, last_col = divmod(end, self._columns)

        for row in range(first_row, last_row + 1):
            col_start = first_col if row == first_row else 0
            col_end = last_col if row == last_row else self._columns - 1
            x1 = (col_start + self._border) * self._cell_width
            y1 = (row + self._border) * self._cell_height
            x2 = (col_end + self._border + 1) * self._cell_width
            y2 = y1 + self._cell_height
            self._canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline="#ffffff",
                width=max(1, self._scale),
                tags=("selection",),
            )
        self._canvas.tag_raise("selection")

    def _copy_selection(self, _event: tk.Event | None = None) -> str:
        if self._selection_anchor is not None and self._selection_end is not None:
            text = self.get_text(self._selection_anchor, self._selection_end)
        else:
            text = self.get_text()

        try:
            self._root.clipboard_clear()
            self._root.clipboard_append(text)
            self._root.update_idletasks()
        except tk.TclError:
            pass
        return "break"
