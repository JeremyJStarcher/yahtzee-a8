#!/usr/bin/env python3
"""
Demonstration of Bitmapped Font Rendering

Shows the difference between Unicode fallback and true 8-bit bitmap fonts.
"""

import argparse

# Import tkinter first (needed by video_display_tk)
import tkinter as tk

from . import video_display_tk as vd


def demo_all_chars() -> None:
    """Display all 256 characters in a grid."""
    print("Creating character set display...")

    # Create a display large enough for all 256 chars (16x16 grid)
    columns = 32
    rows = 8
    scale = 2

    video = vd.Video(rows, columns, scale=scale)

    print(f"Display size: {columns} columns x {rows} rows @ {scale}x scale")
    print("Showing all 256 characters from atascii.yaff font file")

    # Fill screen with character indices
    for i in range(min(256, rows * columns)):
        video.set_screen(i, i)

        # Set contrasting colors - alternate color schemes
        if (i // columns) % 2 == 0:
            # Even rows: Blue background, Yellow text
            video.set_color(i, 0x67)
        else:
            # Odd rows: Black background, Cyan text
            video.set_color(i, 0x03)

    video.refresh_screen()

    print("\nYou should see:")
    print("  - All 256 ASCII/ATASCII characters rendered as pixel art")
    print("  - Each character is exactly 8×8 pixels before scaling")
    print("  - Authentic 8-bit computer look!")
    print("\nClick the window's close button when done.")

    try:
        video._root.mainloop()
    except tk.TclError:
        pass


def demo_text_comparison() -> None:
    """Compare bitmap vs Unicode rendering."""
    print("\n\n=== BITMAP FONT DEMO ===")
    print("This will show 'Hello World' using true bitmapped fonts")

    columns = 20
    rows = 3
    scale = 4

    video = vd.Video(rows, columns, scale=scale, border=1)

    message = "HELLO WORLD! "

    # Row 0: Regular text with default colors
    for i, char in enumerate(message[:columns]):
        video.set_screen(columns + i, ord(char))

    # Row 1: Same text but inverted colors (white on black)
    for i, char in enumerate(message[:columns]):
        offset = columns * 2 + i
        video.set_screen(offset, ord(char))
        video.set_color(offset, 0x01)  # White bg, Black fg (inverted!)

    video.refresh_screen()

    print(f"\nDisplay shows '{message.strip()}' twice:")
    print("  - Top row: Blue background, Yellow text (default C64 colors)")
    print("  - Bottom row: White background, Black text (inverted!)")
    print("\nEach character is rendered from the .yaff bitmap file,")
    print("not from system Unicode fonts.")
    print("\nClick close when done viewing.")

    try:
        video._root.mainloop()
    except tk.TclError:
        pass


def demo_graphics_chars() -> None:
    """Show off graphics/box-drawing characters."""
    print("\n\n=== GRAPHICS CHARACTERS ===")
    print("Showing ATASCII special graphics characters...")

    columns = 40
    rows = 12
    scale = 3

    video = vd.Video(rows, columns, scale=scale, border=1)

    # Draw a box using line drawing characters
    # Top border (row 1, cols 2-37)
    for col in range(2, columns - 2):
        offset = columns + col
        video.set_screen(offset, 0x12)  # ─
        video.set_color(offset, 0x67)

    # Bottom border (row rows-2, cols 2-37)
    for col in range(2, columns - 2):
        offset = columns * (rows - 2) + col
        video.set_screen(offset, 0x12)  # ─
        video.set_color(offset, 0x67)

    # Left border (col 2, rows 2 to rows-3)
    for row in range(2, rows - 2):
        offset = row * columns + 2
        video.set_screen(offset, 0x1D)  # │
        video.set_color(offset, 0x6F)  # Orange on blue

    # Right border (col columns-3, rows 2 to rows-3)
    for row in range(2, rows - 2):
        offset = row * columns + (columns - 3)
        video.set_screen(offset, 0x1D)  # │
        video.set_color(offset, 0x6F)  # Orange on blue

    # Corners
    # Top-left: 0x11 = ┌
    video.set_screen(columns + 2, 0x11)
    video.set_color(columns + 2, 0xE7)  # Light green on yellow!

    # Top-right: 0x17 = ┐
    video.set_screen(columns + (columns - 3), 0x17)
    video.set_color(columns + (columns - 3), 0xE7)

    # Bottom-left: 0x16 = └
    video.set_screen(columns * (rows - 2) + 2, 0x16)
    video.set_color(columns * (rows - 2) + 2, 0xE7)

    # Bottom-right: 0x19 = ┘
    video.set_screen(columns * (rows - 2) + (columns - 3), 0x19)
    video.set_color(columns * (rows - 2) + (columns - 3), 0xE7)

    # Fill center with some content
    for row in range(4, rows - 4):
        for col in range(5, columns - 5):
            if (row + col) % 3 == 0:
                offset = row * columns + col
                video.set_screen(offset, ord("X"))
                video.set_color(offset, 0x54)  # Purple on green

    video.refresh_screen()

    print("\nYou should see:")
    print("  - A box drawn using ATASCII line-drawing characters")
    print("  - Corners and borders from the bitmap font")
    print("  - Pattern inside showing color variety")
    print("\nThis demonstrates that special graphics characters work!")
    print("Click close when done.")

    try:
        video._root.mainloop()
    except tk.TclError:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bitmap Font Rendering Demonstrations")
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["1", "2", "3"],
        default=None,
        help="Demo mode: 1=All chars grid, 2=Text comparison, 3=Graphics chars",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("BITMAP FONT RENDERING DEMONSTRATIONS")
    print("=" * 60)

    if args.mode is None:
        print("\nChoose a demo:")
        print("  1. All 256 characters grid")
        print("  2. Text comparison (bitmap vs Unicode)")
        print("  3. Graphics characters (box drawing)")
        print()
        choice = input("Enter choice (1-3, or just press Enter for #1): ").strip()
    else:
        choice = args.mode

    if choice == "2":
        demo_text_comparison()
    elif choice == "3":
        demo_graphics_chars()
    else:
        demo_all_chars()
