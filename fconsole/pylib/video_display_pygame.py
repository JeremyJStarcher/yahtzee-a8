"""
Pygame Video Display Component for the 8-bit Computer Emulator

The ``pygame`` display output.  Drop-in alternative to
``pylib.video_display_tk.Video`` and ``pylib.video_display_text.Video``
that renders each character cell as scaled 8×8 pixel glyphs from the
embedded font using a Pygame window.

Requires the third-party ``pygame`` package, which is imported lazily so
that the other display outputs remain usable without it.
"""

from __future__ import annotations

import heapq
import time
from collections.abc import Callable

from .font import FONT_DATA
from .video_base import BaseVideo


class Video(BaseVideo):
    """A pygame-rendered video display with character and color memory."""

    # Bitmap glyph data indexed by screen code (populated from FONT_DATA)
    _font_glyphs: dict[int, bytearray] = {}

    @classmethod
    def _build_font_mappings(cls) -> None:
        """Build ``_font_glyphs`` from embedded ``FONT_DATA``.

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

        # Pygame is imported lazily (and kept on the instance) so that this
        # module can be imported without the optional dependency installed.
        import pygame  # pyrefly: ignore[missing-import]

        self._pygame = pygame
        pygame.init()

        width = (columns + 2 * border) * self.CHAR_WIDTH * scale
        height = (rows + 2 * border) * self.CHAR_HEIGHT * scale
        self._screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(
            f"Video Display ({rows}x{columns}) [scale={scale}x][border={border}]"
        )

        self._running = True
        self._close_handler: Callable[[], None] | None = None

        # Sorted queue of (deadline, sequence, callback) scheduled via
        # ``schedule()``; processed by ``pump()`` inside the pygame loop.
        self._scheduled: list[tuple[float, int, Callable[[], None]]] = []
        self._schedule_counter = 0

        # Per-cell change tracking (only changed cells are redrawn)
        self._prev_screen = bytearray(len(self._screen_memory))
        self._prev_color = bytearray(len(self._color_memory))

        # Initial draw
        self.refresh_screen()

    # -- Window / event-loop interface ----------------------------------------

    def set_title(self, title: str) -> None:
        """Set the window title."""
        self._pygame.display.set_caption(title)

    def set_close_handler(self, callback: Callable[[], None]) -> None:
        """Register *callback* to run when the user closes the window."""
        self._close_handler = callback

    def schedule(self, delay_ms: int, callback: Callable[[], None]) -> None:
        """Run *callback* after *delay_ms* milliseconds on the UI thread."""
        deadline = time.perf_counter() + delay_ms / 1000.0
        heapq.heappush(self._scheduled, (deadline, self._schedule_counter, callback))
        self._schedule_counter += 1

    def pump(self) -> None:
        """Process pending events and due scheduled callbacks (non-blocking)."""
        if not self._running:
            return

        for event in self._pygame.event.get():
            if event.type == self._pygame.QUIT:
                self._running = False
                handler = self._close_handler
                if handler is not None:
                    handler()
                return

            if event.type == self._pygame.KEYDOWN:
                flags = 0
                if event.mod & self._pygame.KMOD_SHIFT:
                    flags |= BaseVideo.KB_FLAG_SHIFT
                if event.mod & self._pygame.KMOD_CTRL:
                    flags |= BaseVideo.KB_FLAG_CTRL
                ascii_val = ord(event.unicode) if event.unicode else 0x00
                # Pass all non-null ASCII values so that control
                # characters (BS 0x08, TAB 0x09, ESC 0x1B, DEL 0x7F,
                # etc.) reach the BIOS keyboard handler.
                if ascii_val != 0x00:
                    self._dispatch_key_event(ascii_val, flags)

        now = time.perf_counter()
        while self._scheduled and self._scheduled[0][0] <= now:
            _, _, callback = heapq.heappop(self._scheduled)
            callback()

        if self._dirty:
            self.refresh_screen()

    def mainloop(self) -> None:
        """Run the pygame event loop until the window is closed."""
        while self._running:
            self.pump()
            time.sleep(0.001)

    # -- Scaling -------------------------------------------------------------

    @BaseVideo.scale.setter
    def scale(self, value: int) -> None:
        """Set a new scaling factor, recreating the pygame window."""
        if not isinstance(value, int) or value < 1:
            raise ValueError("Scale must be a positive integer >= 1")

        if value != self._scale:
            self._scale = value
            self._dirty = True

            width = (self._columns + 2 * self._border) * self.CHAR_WIDTH * value
            height = (self._rows + 2 * self._border) * self.CHAR_HEIGHT * value
            self._screen = self._pygame.display.set_mode((width, height))

            # Force a full redraw at the new scale
            self._prev_screen = bytearray(len(self._screen_memory))
            self._prev_color = bytearray(len(self._color_memory))
            self.refresh_screen()

    # -- Color helpers -------------------------------------------------------

    def _get_colors(
        self, color_byte: int
    ) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        """Extract (bg_rgb, fg_rgb) tuples from a color byte."""
        bg_index = min((color_byte >> 4) & 0x0F, 15)
        fg_index = min(color_byte & 0x0F, 15)
        return self.C64_COLORS[bg_index], self.C64_COLORS[fg_index]

    # -- Refresh -------------------------------------------------------------

    def refresh_screen(self) -> None:
        """Redraw all changed cells onto the pygame window."""
        if not self._running:
            return

        width = self.CHAR_WIDTH * self._scale
        height = self.CHAR_HEIGHT * self._scale

        for offset in range(len(self._screen_memory)):
            char_byte = self._screen_memory[offset]
            color_byte = self._color_memory[offset]

            if (
                self._prev_screen[offset] == char_byte
                and self._prev_color[offset] == color_byte
            ):
                continue

            self._prev_screen[offset] = char_byte
            self._prev_color[offset] = color_byte

            row, col = divmod(offset, self._columns)
            x = (col + self._border) * width
            y = (row + self._border) * height

            bg_rgb, fg_rgb = self._get_colors(color_byte)
            self._screen.fill(bg_rgb, (x, y, width, height))

            glyph_data = self._font_glyphs.get(char_byte, bytearray(8))
            for glyph_row in range(self.CHAR_HEIGHT):
                byte_value = glyph_data[glyph_row]
                for glyph_col in range(self.CHAR_WIDTH):
                    if byte_value & (1 << glyph_col):
                        pixel_x = x + glyph_col * self._scale
                        pixel_y = y + glyph_row * self._scale
                        self._screen.fill(
                            fg_rgb,
                            (pixel_x, pixel_y, self._scale, self._scale),
                        )

        self._dirty = False
        self._pygame.display.flip()

    # -- Cleanup -------------------------------------------------------------

    def close(self) -> None:
        """Quit pygame and release the window."""
        self._running = False
        try:
            self._pygame.quit()
        except Exception:
            pass
