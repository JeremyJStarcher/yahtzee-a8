#!/usr/bin/env python3
"""
Test suite and demonstrations for Video Display Component

Validates implementation against Video_Display_Specification.md requirements,
and includes demonstration functions showing various display capabilities.
"""

import sys
import tkinter as tk

from . import video_display as vd


def hello_world() -> None:
    """Simple demonstration - displays 'Hello World' on a Video display."""

    # Create a video display (24 columns x 1 row is enough for "Hello World")
    print("Opening video display...")
    video = vd.Video(1, 24)

    # Set up the text "Hello World"
    message = "Hello World"

    # Write each character to screen memory
    for i, char in enumerate(message):
        # Convert character to byte value
        char_byte = ord(char)
        video.set_screen(i, char_byte)

    # Refresh to show the text
    video.refresh_screen()

    print(f"Displaying: '{message}'")
    print("Click the window's close button to exit.")

    # Wait for user to close the window
    try:
        video._root.mainloop()
    except tk.TclError:
        pass

    print("Window closed.")


def test_pattern() -> None:
    """
    Display a test pattern that fills the entire screen.

    Shows numbered rows with dots and an exclamation mark at the end
    so you can see all lines and verify all columns are working.
    """
    print("Creating test pattern display...")

    # Create a display with 64 columns and 16 rows (scaled by 2x for visibility)
    columns = 40
    rows = 24
    scale = 3

    video = vd.Video(rows, columns, scale=scale)

    print(f"Display size: {columns} columns x {rows} rows")
    print(f"Scale factor: {scale}x")
    print(
        "Each row shows: 'LineX' + dots filling remaining space + '!' at column",
        columns - 1,
    )
    print("\nFilling screen with test pattern...")

    # Fill each row with "LineXX.......................!"
    for row in range(rows):
        # Calculate offset for start of this row
        row_start = row * columns

        # Write "Line" prefix
        prefix = f"Line{row}"
        for i, char in enumerate(prefix):
            if row_start + i < len(video._screen_memory):
                video.set_screen(row_start + i, ord(char))

        # Fill with dots until we reach the second-to-last position
        dot_position = row_start + len(prefix)
        end_position = row_start + columns - 1

        while dot_position < end_position:
            video.set_screen(dot_position, ord("."))
            dot_position += 1

        # Put exclamation mark at the very last position
        if end_position < len(video._screen_memory):
            video.set_screen(end_position, ord("!"))

    # Also set a distinctive color to make it easier to see
    # White background (0x01) with black text (0x00)
    #    for offset in range(len(video._color_memory)):
    #        video.set_color(offset, 0x10)  # bg=White(1), fg=Black(0)

    # Refresh to show everything
    video.refresh_screen()

    print("\nDisplay filled!")
    print("You should see:")
    print(f"  - {rows} numbered rows")
    print("  - Each row starts with 'Line<number>'")
    print("  - Dots filling most of each line")
    print(f"  - Exclamation mark '!' at column {columns - 1} of every row")
    print("\nClick the window's close button when done.")

    # Wait for user to close the window
    try:
        video._root.mainloop()
    except tk.TclError:
        pass

    print("Window closed.")


def test_pattern_animated() -> None:
    """
    Display an animated test pattern that cycles colors every 5 seconds.

    This demonstrates how to update the display in real-time without blocking,
    showing integration with Tkinter's event loop using after().
    """
    print("Creating animated color cycle display...")

    columns = 64
    rows = 16
    scale = 2

    video = vd.Video(rows, columns, scale=scale)

    print(f"Display size: {columns} columns x {rows} rows")
    print(f"Scale factor: {scale}x")
    print("Colors will cycle every 5 seconds")
    print("\nFilling screen with test pattern...")

    # Set up the static text content (same as before)
    for row in range(rows):
        row_start = row * columns

        prefix = f"Line{row}"
        for i, char in enumerate(prefix):
            if row_start + i < len(video._screen_memory):
                video.set_screen(row_start + i, ord(char))

        dot_position = row_start + len(prefix)
        end_position = row_start + columns - 1

        while dot_position < end_position:
            video.set_screen(dot_position, ord("."))
            dot_position += 1

        if end_position < len(video._screen_memory):
            video.set_screen(end_position, ord("!"))

    # Color cycling state
    color_cycle_state = {"step": 0, "running": True}

    def update_colors() -> None:
        """Update all cell colors based on current step."""
        # Cycle through different color combinations
        step = color_cycle_state["step"]

        # Create varying color patterns
        if step % 4 == 0:
            # Blue background, Yellow foreground (original)
            base_color = 0x67
        elif step % 4 == 1:
            # White background, Black text
            base_color = 0x10
        elif step % 4 == 2:
            # Black background, Cyan text
            base_color = 0x03
        else:  # step % 4 == 3
            # Purple background, Green texty
            base_color = 0x54

        print(f"  Updating colors to pattern {step % 4 + 1}/4...")

        # Apply the same color to all cells for this step
        for offset in range(len(video._color_memory)):
            video.set_color(offset, base_color)

        # Refresh screen immediately after updating colors
        video.refresh_screen()

        # Increment and schedule next update
        color_cycle_state["step"] += 1

        if color_cycle_state["running"]:
            # Schedule next color change in 5000ms (5 seconds)
            video._root.after(5000, update_colors)

    def on_closing() -> None:
        """Handle window close event."""
        color_cycle_state["running"] = False
        video.close()

    # Start the color cycling
    update_colors()

    # Initial refresh
    video.refresh_screen()

    print("\nDisplay ready!")
    print("Colors will cycle every 5 seconds:")
    print("  0s: Blue bg / Yellow fg")
    print("  5s: White bg / Black fg")
    print(" 10s: Black bg / Cyan fg")
    print(" 15s: Purple bg / Green fg")
    print(" 20s: Repeat...")
    print("\nClick the window's close button when done.")

    # Set up window close handler
    video._root.protocol("WM_DELETE_WINDOW", on_closing)

    # Use mainloop - it won't block because after() handles updates
    try:
        video._root.mainloop()
    except tk.TclError:
        pass

    print("Window closed.")


def test_constructor() -> bool:
    """Test constructor parameter validation."""
    print("Testing constructor...")

    # Valid construction
    try:
        v = vd.Video(10, 20)
        assert v._rows == 10
        assert v._columns == 20
        assert len(v._screen_memory) == 200
        assert len(v._color_memory) == 200
        print("✓ Valid construction works")
        v.close()
    except Exception as e:
        print(f"✗ Valid construction failed: {e}")
        return False

    # Invalid: non-integer rows
    try:
        v = vd.Video(5.5, 10)
        print("✗ Should reject float rows")
        v.close()
        return False
    except TypeError:
        print("✓ Rejects non-integer rows (TypeError)")

    # Invalid: zero rows
    try:
        v = vd.Video(0, 10)
        print("✗ Should reject zero rows")
        v.close()
        return False
    except ValueError:
        print("✓ Rejects zero rows (ValueError)")

    # Invalid: negative columns
    try:
        v = vd.Video(10, -5)
        print("✗ Should reject negative columns")
        v.close()
        return False
    except ValueError:
        print("✓ Rejects negative columns (ValueError)")

    return True


def test_memory_initialization() -> bool:
    """Test that memory is initialized correctly."""
    print("\nTesting memory initialization...")

    v = vd.Video(5, 10)

    # Screen memory should be filled with 0x20 (space)
    all_spaces = all(c == 0x20 for c in v._screen_memory)
    if all_spaces:
        print("✓ Screen memory initialized to 0x20 (space)")
    else:
        print("✗ Screen memory not properly initialized")
        v.close()
        return False

    # Color memory should be filled with DEFAULT_COLOR (0x67)
    default_color = vd.Video.DEFAULT_COLOR
    all_default = all(c == default_color for c in v._color_memory)
    if all_default:
        print(f"✓ Color memory initialized to 0x{default_color:02X} (DEFAULT_COLOR)")
    else:
        print("✗ Color memory not properly initialized")
        v.close()
        return False

    v.close()
    return True


def test_offset_validation() -> bool:
    """Test offset validation and IndexError handling."""
    print("\nTesting offset validation...")

    v = vd.Video(10, 20)  # 200 cells total

    # Valid offsets
    try:
        v.get_screen(0)
        v.get_screen(199)
        print("✓ Valid offsets accepted (0 and size-1)")
    except Exception as e:
        print(f"✗ Valid offsets rejected: {e}")
        v.close()
        return False

    # Invalid: negative offset
    try:
        v.get_screen(-1)
        print("✗ Should reject negative offset")
        v.close()
        return False
    except IndexError:
        print("✓ Rejects negative offset (IndexError)")

    # Invalid: offset >= size
    try:
        v.get_screen(200)
        print("✗ Should reject offset >= size")
        v.close()
        return False
    except IndexError:
        print("✓ Rejects offset >= size (IndexError)")

    # Invalid: non-integer offset
    try:
        v.get_screen(5.5)
        print("✗ Should reject non-integer offset")
        v.close()
        return False
    except TypeError:
        print("✓ Rejects non-integer offset (TypeError)")

    v.close()
    return True


def test_screen_memory() -> bool:
    """Test set_screen/get_screen operations."""
    print("\nTesting screen memory...")

    v = vd.Video(10, 20)

    # Set and get a value
    v.set_screen(50, ord("A"))
    val = v.get_screen(50)
    if val == ord("A"):
        print(f"✓ set_screen/get_screen works (got {val})")
    else:
        print(f"✗ Expected {ord('A')}, got {val}")
        v.close()
        return False

    # Value masking (> 255 should be masked to 0xFF)
    v.set_screen(51, 300)  # 300 & 0xFF = 44
    val = v.get_screen(51)
    if val == 44:
        print(f"✓ Values masked with 0xFF ({val})")
    else:
        print(f"✗ Expected 44, got {val}")
        v.close()
        return False

    v.close()
    return True


def test_color_memory() -> bool:
    """Test set_color/get_color operations."""
    print("\nTesting color memory...")

    v = vd.Video(10, 20)

    # Set and get a value
    v.set_color(50, 0xAB)
    val = v.get_color(50)
    if val == 0xAB:
        print(f"✓ set_color/get_color works (got 0x{val:02X})")
    else:
        print(f"✗ Expected 0xAB, got 0x{val:02X}")
        v.close()
        return False

    # Value masking
    v.set_color(51, 999)  # 999 & 0xFF = 231
    val = v.get_color(51)
    if val == 231:
        print(f"✓ Values masked with 0xFF ({val})")
    else:
        print(f"✗ Expected 231, got {val}")
        v.close()
        return False

    # Extract colors from byte
    bg_rgb, fg_rgb = v._get_colors(0x67)  # Blue bg, Yellow fg
    expected_bg = vd.Video.C64_COLORS[6]  # Blue
    expected_fg = vd.Video.C64_COLORS[7]  # Yellow
    if bg_rgb == expected_bg and fg_rgb == expected_fg:
        print("✓ Color extraction works correctly")
    else:
        print("✗ Color extraction failed")
        v.close()
        return False

    v.close()
    return True


def test_default_color() -> bool:
    """Test default color value."""
    print("\nTesting default color...")

    v = vd.Video(10, 20)

    # Default should be 0x67 (Blue background, Yellow foreground)
    default = v.DEFAULT_COLOR
    if default == 0x67:
        print(f"✓ DEFAULT_COLOR is 0x{default:02X} (Blue bg / Yellow fg)")
    else:
        print(f"✗ DEFAULT_COLOR is 0x{default:02X}, expected 0x67")
        v.close()
        return False

    # Verify first cell has default color
    val = v.get_color(0)
    if val == 0x67:
        print("✓ Cells initialized with DEFAULT_COLOR")
    else:
        print(f"✗ Expected 0x67, got 0x{val:02X}")
        v.close()
        return False

    v.close()
    return True


def test_multiple_displays() -> bool:
    """Test that multiple displays can coexist independently."""
    print("\nTesting multiple displays...")

    try:
        v1 = vd.Video(10, 20)
        v2 = vd.Video(5, 10)

        # Set different values in each display
        v1.set_screen(0, ord("A"))
        v2.set_screen(0, ord("B"))

        # Verify independence
        if v1.get_screen(0) == ord("A") and v2.get_screen(0) == ord("B"):
            print("✓ Multiple displays are independent")
        else:
            print("✗ Displays appear to share memory")
            v1.close()
            v2.close()
            return False

        # Close one, verify other still works
        v1.close()
        val = v2.get_screen(0)
        if val == ord("B"):
            print("✓ Closing one display doesn't affect others")
        else:
            print("✗ Closing display affected other")
            v2.close()
            return False

        v2.close()
        return True
    except Exception as e:
        print(f"✗ Multiple displays test failed: {e}")
        return False


def test_dirty_tracking() -> bool:
    """Test that dirty flag is set correctly."""
    print("\nTesting dirty tracking...")

    v = vd.Video(10, 20)

    # Initially dirty (for initial draw)
    if not hasattr(v, "_dirty"):
        print("✗ No _dirty attribute")
        v.close()
        return False

    # After refresh, should not be dirty
    v.refresh_screen()
    if not v._dirty:
        print("✓ Dirty flag cleared after refresh")
    else:
        print("✗ Dirty flag not cleared after refresh")
        v.close()
        return False

    # Setting a value should mark dirty
    v.set_screen(50, ord("X"))
    if v._dirty:
        print("✓ set_screen marks display as dirty")
    else:
        print("✗ set_screen didn't mark dirty")
        v.close()
        return False

    # Setting same value shouldn't change dirty state unnecessarily
    current = v.get_screen(50)
    v.set_screen(50, current)  # Set to same value
    # It might still be dirty from previous set, but let's check it doesn't get dirtier
    print(f"  Note: dirty state after setting same value: {v._dirty}")

    v.close()
    return True


def test_character_set() -> bool:
    """Test character set indexing."""
    print("\nTesting character set...")

    v = vd.Video(10, 20)

    # Space at index 0x20
    space_char = v._get_char_display(0x20)
    if space_char == " ":
        print("✓ Space character (0x20) correct")
    else:
        print(f"✗ Expected ' ', got '{space_char}'")
        v.close()
        return False

    # Check array has 128 elements
    if len(v.CHARS) == 128:
        print("✓ Character set has 128 entries")
    else:
        print(f"✗ Character set has {len(v.CHARS)} entries, expected 128")
        v.close()
        return False

    # Test some characters from specification
    test_chars = [
        (0x00, "♥"),
        (0x01, "├"),
        (0x20, " "),
        (0x41, "A"),  # 'A'
        (0x61, "a"),  # 'a'
    ]

    all_correct = True
    for idx, expected in test_chars:
        actual = v._get_char_display(idx)
        if actual != expected:
            print(f"✗ Index 0x{idx:02X}: expected '{expected}', got '{actual}'")
            all_correct = False

    if all_correct:
        print("✓ Sample characters from specification match")

    v.close()
    return True


def main() -> int:
    """Run all tests."""
    print("=" * 60)
    print("Video Display Component - Specification Compliance Tests")
    print("=" * 60)

    tests = [
        ("Constructor", test_constructor),
        ("Memory Initialization", test_memory_initialization),
        ("Offset Validation", test_offset_validation),
        ("Screen Memory", test_screen_memory),
        ("Color Memory", test_color_memory),
        ("Default Color", test_default_color),
        ("Multiple Displays", test_multiple_displays),
        ("Dirty Tracking", test_dirty_tracking),
        ("Character Set", test_character_set),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗ Test raised exception: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\nALL TESTS PASSED!")
        return 0
    else:
        print(f"\n{total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
