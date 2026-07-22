"""
Video Display Component for 8-bit Computer Emulator

Implements a Tkinter-based video display subsystem supporting multiple
simultaneous Video instances, each with its own window, screen memory,
and color memory.
"""

import tkinter as tk
from tkinter import Canvas

from .font_parser import load_font


class Video:
    """A single video display instance managing its own window and memory."""

    # Character set - 128 characters (0x00-0x7F)
    CHARS = [
        "♥","├","🮇","┘","┤","┐","╱","╲","◢","▗","◣","▝","▘","🮂","▂","▖",
        "♣","┌","─","┼","•","▄","▎","┬","┴","▌","└","␛","↑","↓","←","→",
        " ","!", '"',"#","$","%","&","'","(",")","*","+",",","-",".","/",
        "0","1","2","3","4","5","6","7","8","9",":",";","<","=",">","?",
        "@","A","B","C","D","E","F","G","H","I","J","K","L","M","N","O",
        "P","Q","R","S","T","U","V","W","X","Y","Z","[","\\","]","^","_",
        "♦","a","b","c","d","e","f","g","h","i","j","k","l","m","n","o",
        "p","q","r","s","t","u","v","w","x","y","z","♠","|","🢰","◀","▶",
    ]

    # Bitmapped font data (loaded from atascii.yaff)
    _font_glyphs: dict[int, bytearray] | None = None

    # Character dimensions in pixels
    CHAR_WIDTH: int = 8
    CHAR_HEIGHT: int = 8

    # Commodore 64 color palette (16 colors)
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

    # Default color: Background=Blue(6), Foreground=Yellow(7)
    DEFAULT_COLOR = 0x67

    def __init__(self, rows, columns, scale: int=1, border: int=1) -> None:
        """
        Create a new video display instance.

        Args:
            rows: Number of character rows (must be positive integer)
            columns: Number of character columns (must be positive integer)
            scale: Optional scaling factor (default 1). Each cell is scaled by this factor.
                   For example, scale=2 makes each 8×8 pixel cell become 16×16 pixels.
            border: Optional border around the display in character units (default 1).
                    Creates padding on all four sides. Use 0 for no border.

        Raises:
            ValueError: If rows or columns are not positive integers, or if scale < 1, or border < 0
            TypeError: If parameters are not correct types
        """
        # Validate parameters
        if not isinstance(rows, int) or not isinstance(columns, int):
            raise TypeError("Rows and columns must be integers")

        if rows <= 0 or columns <= 0:
            raise ValueError("Rows and columns must be positive integers")

        if not isinstance(scale, int) or scale < 1:
            raise ValueError("Scale must be a positive integer >= 1")

        if not isinstance(border, int) or border < 0:
            raise ValueError("Border must be a non-negative integer")

        self._rows = rows
        self._columns = columns
        self._scale = scale
        self._border = border
        self._root: tk.Tk
        self._canvas: Canvas

        # Load bitmapped font if not already loaded
        if Video._font_glyphs is None:
            try:
                Video._font_glyphs = load_font('atascii.yaff')._glyphs
            except Exception as e:
                print(f"Warning: Could not load bitmapped font: {e}")
                Video._font_glyphs = {}

        # Initialize memory arrays with space characters and default color
        total_cells = rows * columns
        self._screen_memory = bytearray([0x20] * total_cells)
        self._color_memory = bytearray([self.DEFAULT_COLOR] * total_cells)

        # Dirty tracking - track which cells need redrawing
        self._dirty = True

        # Create Tkinter window and canvas
        self._root = tk.Tk()
        self._root.title(f"Video Display ({rows}x{columns}) [scale={scale}x][border={border}]")

        # Calculate display size including border (scaled by character dimensions)
        # Border adds padding on both sides: left+right or top+bottom
        width = (columns + 2 * border) * self.CHAR_WIDTH * scale
        height = (rows + 2 * border) * self.CHAR_HEIGHT * scale

        self._canvas = tk.Canvas(
            self._root,
            width=width,
            height=height,
            bg='black',
            highlightthickness=0
        )
        self._canvas.pack()

        # Store rectangle references for dirty-rectangle optimization
        self._cell_rects = {}

        # Initial draw
        self.refresh_screen()

    @property
    def scale(self) -> int:
        """Get the current scaling factor."""
        return self._scale

    @scale.setter
    def scale(self, value) -> None:
        """
        Set a new scaling factor.

        Args:
            value: New scale factor (must be positive integer >= 1)

        Raises:
            ValueError: If value is not valid
        """
        if not isinstance(value, int) or value < 1:
            raise ValueError("Scale must be a positive integer >= 1")

        if value != self._scale:
            self._scale = value
            self._dirty = True

            # Resize window and canvas
            width = self._columns * self.CHAR_WIDTH * value
            height = self._rows * self.CHAR_HEIGHT * value

            self._root.title(f"Video Display ({self._rows}x{self._columns}) [scale={value}x]")
            self._canvas.config(width=width, height=height)

            # Force redraw on next refresh
            self.refresh_screen()

    def _validate_offset(self, offset) -> bool:
        """
        Validate that an offset is within valid range.

        Args:
            offset: Memory offset to validate

        Returns:
            True if valid

        Raises:
            IndexError: If offset is out of range
            TypeError: If offset is not numeric
        """
        if not isinstance(offset, int):
            raise TypeError("Offset must be an integer")

        total_cells = self._rows * self._columns
        if offset < 0 or offset >= total_cells:
            raise IndexError(f"Offset {offset} out of range [0, {total_cells - 1}]")

        return True

    def set_screen(self, offset, character) -> None:
        """
        Set a character in screen memory.

        Args:
            offset: Cell offset (row-major order)
            character: Character byte value (will be masked with 0xFF)

        Raises:
            IndexError: If offset is invalid
            TypeError: If parameters are not correct types
        """
        self._validate_offset(offset)

        # Mask the character value
        char_byte = character & 0xFF

        # Only update and mark dirty if changed
        if self._screen_memory[offset] != char_byte:
            self._screen_memory[offset] = char_byte
            self._dirty = True

    def get_screen(self, offset):
        """
        Get a character from screen memory.

        Args:
            offset: Cell offset (row-major order)

        Returns:
            The character byte at that offset

        Raises:
            IndexError: If offset is invalid
            TypeError: If offset is not an integer
        """
        self._validate_offset(offset)
        return self._screen_memory[offset]

    def set_color(self, offset, color) -> None:
        """
        Set a color byte in color memory.

        Args:
            offset: Cell offset (row-major order)
            color: Color byte (bits 7-4: background, bits 3-0: foreground)
                   Will be masked with 0xFF

        Raises:
            IndexError: If offset is invalid
            TypeError: If parameters are not correct types
        """
        self._validate_offset(offset)

        # Mask the color value
        color_byte = color & 0xFF

        # Only update and mark dirty if changed
        if self._color_memory[offset] != color_byte:
            self._color_memory[offset] = color_byte
            self._dirty = True

    def get_color(self, offset):
        """
        Get a color byte from color memory.

        Args:
            offset: Cell offset (row-major order)

        Returns:
            The color byte at that offset

        Raises:
            IndexError: If offset is invalid
            TypeError: If offset is not an integer
        """
        self._validate_offset(offset)
        return self._color_memory[offset]

    def _get_char_display(self, char_byte: int) -> str:
        """
        Convert a character byte to displayable string.

        High bit is ignored (masked off).

        Args:
            char_byte: Character byte value

        Returns:
            String representation of the character
        """
        index = char_byte & 0x7F
        if index < len(self.CHARS):
            return self.CHARS[index]
        else:
            return "?"

    def _draw_bitmap_char(self, canvas: Canvas, x: int, y: int, char_byte: int, fg_color: str, bg_color: str, scale: int) -> bool:
        """
        Draw a single character using bitmap data from font file.

        Uses pixel-by-pixel rectangle drawing for authentic 8-bit look.

        Args:
            canvas: Tkinter canvas to draw on
            x, y: Top-left corner position in pixels
            char_byte: Character byte (high bit masked)
            fg_color: Foreground color hex string
            bg_color: Background color hex string
            scale: Scaling factor
        """
        # Get glyph data - mask high bit but check both with and without it
        glyph_index = char_byte & 0xFF

        # Try full byte first, then masked version
        glyph_data = None
        if Video._font_glyphs:
            glyph_data = Video._font_glyphs.get(glyph_index)
            if glyph_data is None:
                # Fall back to CHARS-based lookup
                index = char_byte & 0x7F
                if index in Video._font_glyphs:
                    glyph_data = Video._font_glyphs[index]

        if glyph_data is None or len(glyph_data) != 8:
            # No bitmap available - fallback to text rendering
            return False

        # Draw background first (fills entire cell)
        canvas.create_rectangle(
            x, y,
            x + self.CHAR_WIDTH * scale, y + self.CHAR_HEIGHT * scale,
            fill=bg_color,
            outline=""
        )

        # Draw foreground pixels where bits are set
        pixel_size = max(1, scale)
        for row in range(self.CHAR_HEIGHT):
            byte_val: int = glyph_data[row]
            for col in range(self.CHAR_WIDTH):
                # Check if this pixel should be drawn
                bit_position = 7 - col  # MSB first
                if byte_val & (1 << bit_position):
                    # Draw a small rectangle for this pixel
                    px = x + col * scale
                    py = y + row * scale
                    canvas.create_rectangle(
                        px, py,
                        px + pixel_size, py + pixel_size,
                        fill=fg_color,
                        outline=""
                    )

        return True

    def _get_colors(self, color_byte: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        """
        Extract background and foreground colors from color byte.

        Args:
            color_byte: Color byte (bits 7-4: bg, bits 3-0: fg)

        Returns:
            Tuple of (background_color_rgb, foreground_color_rgb)
        """
        bg_index = (color_byte >> 4) & 0x0F
        fg_index = color_byte & 0x0F

        # Clamp to valid range
        bg_index = min(bg_index, 15)
        fg_index = min(fg_index, 15)

        bg_color = self.C64_COLORS[bg_index]
        fg_color = self.C64_COLORS[fg_index]

        return bg_color, fg_color

    def refresh_screen(self) -> None:
        """
        Refresh the display by redrawing all cells.

        This method:
        1. Redraws the display
        2. Processes pending Tkinter events
        3. Keeps the window responsive
        4. Is safe to call when nothing changed
        """
        if not hasattr(self, '_canvas') or self._canvas is None:
            return

        # Only redraw if something changed or canvas doesn't exist
        if not self._dirty and self._cell_rects:
            # Still process events even if not dirty
            try:
                self._root.update_idletasks()
            except tk.TclError:
                pass  # Window was closed
            return

        # Clear canvas
        self._canvas.delete("all")
        self._cell_rects.clear()

        # Track if we successfully used bitmapped fonts
        bitmap_render_success = True

        # First pass: try to draw with bitmaps
        for offset in range(len(self._screen_memory)):
            row = offset // self._columns
            col = offset % self._columns

            char_byte = self._screen_memory[offset]
            color_byte = self._color_memory[offset]

            # Get colors
            bg_color_rgb, fg_color_rgb = self._get_colors(color_byte)

            # Convert RGB tuples to hex strings for Tkinter
            bg_hex = f"#{bg_color_rgb[0]:02x}{bg_color_rgb[1]:02x}{bg_color_rgb[2]:02x}"
            fg_hex = f"#{fg_color_rgb[0]:02x}{fg_color_rgb[1]:02x}{fg_color_rgb[2]:02x}"

            # Calculate pixel position (with scaling and border offset)
            x = (col + self._border) * self.CHAR_WIDTH * self._scale
            y = (row + self._border) * self.CHAR_HEIGHT * self._scale

            # Try to draw using bitmapped font
            if not self._draw_bitmap_char(
                self._canvas, x, y, char_byte,
                fg_hex, bg_hex, self._scale
            ):
                bitmap_render_success = False

                # Fallback: use background rectangle + text
                rect_id = self._canvas.create_rectangle(
                    x, y,
                    x + self.CHAR_WIDTH * self._scale, y + self.CHAR_HEIGHT * self._scale,
                    fill=bg_hex,
                    outline=""
                )

                # Draw character using Unicode fallback
                char_str = self._get_char_display(char_byte)
                font_size = max(1, int(self.CHAR_HEIGHT * self._scale))
                text_id = self._canvas.create_text(
                    x + (self.CHAR_WIDTH // 2) * self._scale,
                    y + (self.CHAR_HEIGHT // 2) * self._scale,
                    text=char_str,
                    font=("Courier", font_size),
                    fill=fg_hex,
                    anchor="center"
                )

                # Store references for fallback rendering
                if offset not in self._cell_rects:
                    self._cell_rects[offset] = []
                self._cell_rects[offset].append((rect_id, text_id))

        # If any cell used fallback, we need to redraw everything next time
        if not bitmap_render_success and Video._font_glyphs:
            print("Warning: Some characters missing from font file, using fallback")

        # Reset dirty flag
        self._dirty = False

        # Process pending events to keep window responsive
        try:
            self._root.update_idletasks()
        except tk.TclError:
            pass  # Window was closed

    def close(self) -> None:
        """Close the display and clean up resources."""
        if hasattr(self, '_root') and self._root is not None:
            try:
                self._root.destroy()
            except Exception:
                pass

