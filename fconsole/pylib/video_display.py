"""
Video Display Component for 8-bit Computer Emulator

Implements a Tkinter-based video display subsystem supporting multiple
simultaneous Video instances, each with its own window, screen memory,
and color memory.  This module uses bitmap PhotoImage cells for authentic
pixel-art rendering.
"""

import tkinter as tk
from tkinter import Canvas, PhotoImage

from .font import FONT_DATA
from .video_base import BaseVideo


class Video(BaseVideo):
    """Bitmap-rendered video display with per-pixel glyph drawing."""

    # Bitmap glyph data indexed by screen code (populated from FONT_DATA)
    _font_glyphs: dict[int, bytearray] = {}

    @classmethod
    def _build_font_mappings(cls) -> None:
        """Build ``_font_glyphs`` dictionary from embedded ``FONT_DATA``.

        Populates the bitmap lookup table so characters can be rendered
        using their 8×8 pixel patterns instead of Unicode fallback.
        Called once, lazily, on first ``Video`` instantiation.
        """
        if cls._font_glyphs:  # Already built
            return

        cls._font_glyphs = {}
        for font_char in FONT_DATA:
            cls._font_glyphs[font_char.screen_order] = bytearray(font_char.layout)

    def __init__(
        self, rows: int, columns: int, scale: int = 1, border: int = 1
    ) -> None:
        super().__init__(rows, columns, scale, border)

        # Build font mappings from embedded FONT_DATA on first use
        Video._build_font_mappings()

        # Bitmap-specific per-cell state
        self._cell_images: dict[int, PhotoImage] = {}
        self._cell_tags: dict[int, int] = {}
        self._prev_screen = bytearray(len(self._screen_memory))
        self._prev_color = bytearray(len(self._color_memory))

        # Create Tkinter window and canvas
        self._root = tk.Tk()
        self._root.title(
            f"Video Display ({rows}x{columns}) [scale={scale}x][border={border}]"
        )

        width = (columns + 2 * border) * self.CHAR_WIDTH * scale
        height = (rows + 2 * border) * self.CHAR_HEIGHT * scale

        self._root.geometry(f"{width}x{height}")
        self._root.resizable(False, False)

        self._canvas = tk.Canvas(
            self._root, width=width, height=height, bg="black", highlightthickness=0
        )
        self._canvas.pack()

        # Initial draw
        self.refresh_screen()

    @BaseVideo.scale.setter
    def scale(self, value: int) -> None:
        """Set a new scaling factor, rebuilding cached images."""
        if not isinstance(value, int) or value < 1:
            raise ValueError("Scale must be a positive integer >= 1")

        if value != self._scale:
            self._scale = value
            self._dirty = True

            # Cached images have dimensions based on the previous scale.
            self._canvas.delete("all")
            self._cell_images.clear()
            self._cell_tags.clear()

            width = (self._columns + 2 * self._border) * self.CHAR_WIDTH * value
            height = (self._rows + 2 * self._border) * self.CHAR_HEIGHT * value

            self._root.title(
                f"Video Display ({self._rows}x{self._columns}) "
                f"[scale={value}x][border={self._border}]"
            )
            self._root.geometry(f"{width}x{height}")
            self._canvas.config(width=width, height=height)

            # Force redraw on next refresh
            self.refresh_screen()

    def _get_colors(
        self, color_byte: int
    ) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        """Extract (bg_rgb, fg_rgb) tuples from a color byte."""
        bg_index = min((color_byte >> 4) & 0x0F, 15)
        fg_index = min(color_byte & 0x0F, 15)
        return self.C64_COLORS[bg_index], self.C64_COLORS[fg_index]

    def refresh_screen(self) -> None:
        """Redraw all cells using bitmap PhotoImage glyphs."""
        if not hasattr(self, "_canvas") or self._canvas is None:
            return

        if not self._dirty:
            try:
                self._root.update_idletasks()
            except tk.TclError:
                pass
            return

        width = self.CHAR_WIDTH * self._scale
        height = self.CHAR_HEIGHT * self._scale

        for offset in range(len(self._screen_memory)):
            char_byte = self._screen_memory[offset]
            color_byte = self._color_memory[offset]

            if (
                self._prev_screen[offset] == char_byte
                and self._prev_color[offset] == color_byte
                and offset in self._cell_images
            ):
                continue

            self._prev_screen[offset] = char_byte
            self._prev_color[offset] = color_byte

            row = offset // self._columns
            col = offset % self._columns
            x = (col + self._border) * width
            y = (row + self._border) * height

            bg_rgb, fg_rgb = self._get_colors(color_byte)
            bg_hex = f"#{bg_rgb[0]:02x}{bg_rgb[1]:02x}{bg_rgb[2]:02x}"
            fg_hex = f"#{fg_rgb[0]:02x}{fg_rgb[1]:02x}{fg_rgb[2]:02x}"

            if offset not in self._cell_images:
                image = PhotoImage(width=width, height=height)
                self._cell_images[offset] = image
                self._cell_tags[offset] = self._canvas.create_image(
                    x, y, image=image, anchor="nw"
                )
            else:
                image = self._cell_images[offset]

            image.put(bg_hex, to=(0, 0, width, height))
            glyph_data = self._font_glyphs.get(char_byte, bytearray(8))
            for glyph_row in range(self.CHAR_HEIGHT):
                byte_value = glyph_data[glyph_row]
                for glyph_col in range(self.CHAR_WIDTH):
                    if byte_value & (1 << glyph_col):
                        pixel_x = glyph_col * self._scale
                        pixel_y = glyph_row * self._scale
                        image.put(
                            fg_hex,
                            to=(
                                pixel_x,
                                pixel_y,
                                pixel_x + self._scale,
                                pixel_y + self._scale,
                            ),
                        )

        self._dirty = False

        try:
            self._root.update_idletasks()
        except tk.TclError:
            pass
