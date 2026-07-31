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


class Video:
    """A native-text video display with character and color memory."""

    # Keep this table identical to the bitmap renderer so screen codes remain
    # interchangeable between the two backends.
    # fmt: off
    CHARS = [
        "▀","▁","▂","▃","▄","▅","▆","▇","█","▉","▊","▋","▌","▍","▎","▏",
        "▐","░","▒","▓","▔","▕","▖","▗","▘","▙","▚","▛","▜","▝","▞","▟",
        " ","!","\"","#","$","%","&","'","(",")","*","+",",","-",".","/",
        "0","1","2","3","4","5","6","7","8","9",":",";","<","=",">","?",
        "@","A","B","C","D","E","F","G","H","I","J","K","L","M","N","O",
        "P","Q","R","S","T","U","V","W","X","Y","Z","[","\\","]","^","_",
        "`","a","b","c","d","e","f","g","h","i","j","k","l","m","n","o",
        "p","q","r","s","t","u","v","w","x","y","z","{","|","}","~","\x7f",
        "─","━","│","┃","┄","┅","┆","┇","┈","┉","┊","┋","┌","┍","┎","┏",
        "┐","┑","┒","┓","└","┕","┖","┗","┘","┙","┚","┛","├","┝","┞","┟",
        "┠","┡","┢","┣","┤","┥","┦","┧","┨","┩","┪","┫","┬","┭","┮","┯",
        "┰","┱","┲","┳","┴","┵","┶","┷","┸","┹","┺","┻","┼","┽","┾","┿",
        "╀","╁","╂","╃","╄","╅","╆","╇","╋","╊","╉","╋","╌","╍","╎","╏",
        "═","║","╒","╓","╔","╕","╖","╗","╘","╙","╚","╛","╜","╝","╞","╟",
        "╠","╡","╢","╣","╤","╥","╦","╧","╨","╩","╪","╫","╬","╭","╮","╯",
        "╰","╱","╲","╳","╴","╵","╶","╷","╸","╹","╺","╻","╼","╽","╿","╾"
    ]
    # fmt: on

    # Logical character dimensions retained for API familiarity.  The actual
    # native-text cell dimensions are derived from the selected Tk font.
    CHAR_WIDTH = 8
    CHAR_HEIGHT = 8

    C64_COLORS = [
        (0x00, 0x00, 0x00),  # 0: Black
        (0xFF, 0xFF, 0xFF),  # 1: White
        (0x68, 0x37, 0x2B),  # 2: Red
        (0x70, 0xA4, 0xB2),  # 3: Cyan
        (0x6F, 0x3D, 0x86),  # 4: Purple
        (0x58, 0x8D, 0x43),  # 5: Green
        (0x35, 0x28, 0x79),  # 6: Blue
        (0xB8, 0xC7, 0x6F),  # 7: Yellow
        (0x6F, 0x4F, 0x25),  # 8: Orange
        (0x43, 0x39, 0x00),  # 9: Brown
        (0x9A, 0x67, 0x59),  # 10: Light Red
        (0x44, 0x44, 0x44),  # 11: Dark Gray
        (0x6C, 0x6C, 0x6C),  # 12: Medium Gray
        (0x9A, 0xD2, 0x84),  # 13: Light Green
        (0x6C, 0x5E, 0xB5),  # 14: Light Blue
        (0x95, 0x95, 0x95),  # 15: Light Gray
    ]

    DEFAULT_COLOR = 0x67

    # Tk normally cannot display U+007F.  This visible Unicode control-picture
    # substitute keeps screen code $7F inspectable in native-text mode.
    _DISPLAY_SUBSTITUTIONS = {0x7F: "␡"}

    _CHAR_TO_CODE: dict[str, int] = {}
    for _index, _character in enumerate(CHARS):
        # Match list.index(): duplicate Unicode glyphs resolve to the first code.
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
        self._validate_dimensions(rows, columns, scale, border)

        self._rows = rows
        self._columns = columns
        self._scale = scale
        self._border = border
        self._requested_font_family = font_family

        total_cells = rows * columns
        self._screen_memory = bytearray([0x20] * total_cells)
        self._color_memory = bytearray([self.DEFAULT_COLOR] * total_cells)
        self._dirty_cells = set(range(total_cells))
        self._dirty = True

        self._root = tk.Tk()
        self._root.title("Native Text Video Display")

        self._canvas = Canvas(self._root, highlightthickness=0, takefocus=True)
        self._canvas.pack()

        self._palette_hex = [
            f"#{red:02x}{green:02x}{blue:02x}" for red, green, blue in self.C64_COLORS
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

    @staticmethod
    def _validate_dimensions(rows: int, columns: int, scale: int, border: int) -> None:
        if not isinstance(rows, int) or not isinstance(columns, int):
            raise TypeError("Rows and columns must be integers")
        if rows <= 0 or columns <= 0:
            raise ValueError("Rows and columns must be positive integers")
        if not isinstance(scale, int) or scale < 1:
            raise ValueError("Scale must be a positive integer >= 1")
        if not isinstance(border, int) or border < 0:
            raise ValueError("Border must be a non-negative integer")

    @property
    def scale(self) -> int:
        return self._scale

    @scale.setter
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

    @property
    def font_family(self) -> str:
        """Return the actual font family selected by Tk."""
        return self._font_family

    @property
    def cell_width(self) -> int:
        return self._cell_width

    @property
    def cell_height(self) -> int:
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
                x1,
                y1,
                x2,
                y2,
                fill=default_bg,
                outline="",
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

    def _validate_offset(self, offset: int) -> None:
        if not isinstance(offset, int):
            raise TypeError("Offset must be an integer")
        if offset < 0 or offset >= len(self._screen_memory):
            raise IndexError(
                f"Offset {offset} out of range [0, {len(self._screen_memory) - 1}]"
            )

    def set_screen(self, offset: int, character: int) -> None:
        self._validate_offset(offset)
        char_byte = character & 0xFF
        if self._screen_memory[offset] == char_byte:
            return
        self._screen_memory[offset] = char_byte
        self._dirty_cells.add(offset)
        self._dirty = True

    def get_screen(self, offset: int) -> int:
        self._validate_offset(offset)
        return self._screen_memory[offset]

    def set_color(self, offset: int, color: int) -> None:
        self._validate_offset(offset)
        color_byte = color & 0xFF
        if self._color_memory[offset] == color_byte:
            return
        self._color_memory[offset] = color_byte
        self._dirty_cells.add(offset)
        self._dirty = True

    def get_color(self, offset: int) -> int:
        self._validate_offset(offset)
        return self._color_memory[offset]

    def _display_character(self, char_byte: int) -> str:
        return self._DISPLAY_SUBSTITUTIONS.get(char_byte, self.CHARS[char_byte])

    def _get_color_hex(self, color_byte: int) -> tuple[str, str]:
        bg_index = (color_byte >> 4) & 0x0F
        fg_index = color_byte & 0x0F
        return self._palette_hex[bg_index], self._palette_hex[fg_index]

    def refresh_screen(self) -> None:
        """Apply only changed cells to the persistent Canvas objects."""
        if not hasattr(self, "_canvas") or self._canvas is None:
            return

        if self._dirty:
            for offset in tuple(self._dirty_cells):
                bg_hex, fg_hex = self._get_color_hex(self._color_memory[offset])
                self._canvas.itemconfigure(self._background_items[offset], fill=bg_hex)
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

    def close(self) -> None:
        if hasattr(self, "_root") and self._root is not None:
            try:
                self._root.destroy()
            except Exception:
                pass
