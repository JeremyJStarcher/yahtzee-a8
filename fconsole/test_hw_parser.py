#!/usr/bin/env python3
"""Quick test to verify hw_limits.inc parser works correctly."""

import traceback

from fcon import parse_hw_limits

# Test parsing the hardware limits file
hw = parse_hw_limits("bios/src/hw_limits.inc")

print("Parsed Hardware Limits:")
print(f"  CLOCK_SPEED: {hw.clock_speed}")
print(f"  SCREEN_COLS: {hw.screen_cols}")
print(f"  SCREEN_ROWS: {hw.screen_rows}")
print(f"  SCREEN_SIZE: {hw.screen_size} (expected: {40 * 24})")
print(f"  START_REGION_CHAR_RAM: ${hw.start_region_char_ram:04X} (expected: $E000)")
print(
    f"  END_REGION_CHAR_RAM: ${hw.end_region_char_ram:04X} (expected: $E000+960=$E3C0)"
)
print(f"  START_REGION_COLOR_RAM: ${hw.start_region_color_ram:04X} (expected: $E400)")
print(
    f"  END_REGION_COLOR_RAM: ${hw.end_region_color_ram:04X} (expected: $E400+960=$E7C0)"
)
print(f"  DEFAULT_COLOR: ${hw.default_color:02X} (expected: $6F=111)")
print(f"  DEFAULT_SCREEN_VAL: {hw.default_screen_val} (expected: screencode for space)")

# Verify values
assert hw.clock_speed == 1000000, f"CLOCK_SPEED mismatch: {hw.clock_speed}"
assert hw.screen_cols == 40, f"SCREEN_COLS mismatch: {hw.screen_cols}"
assert hw.screen_rows == 24, f"SCREEN_ROWS mismatch: {hw.screen_rows}"
assert hw.screen_size == 960, f"SCREEN_SIZE mismatch: {hw.screen_size}"

# Second pass: verify the parser works when called programmatically
try:
    hw2 = parse_hw_limits("bios/src/hw_limits.inc")
    print("\n✓ Parser re-executed successfully!")
    print("\nHardware Configuration:")
    print(f"  Clock Speed: {hw2.clock_speed:,} Hz")
    print(f"  Screen Size: {hw2.screen_cols}x{hw2.screen_rows} ({hw2.screen_size} cells)")
    print(f"  Char RAM: ${hw2.start_region_char_ram:04X}-${hw2.end_region_char_ram:04X}")
    print(
        f"  Color RAM: ${hw2.start_region_color_ram:04X}-${hw2.end_region_color_ram:04X}"
    )
    print(f"  Default Color: ${hw2.default_color:02X}")
except Exception as e:
    print(f"\n✗ Error: {e}")
    traceback.print_exc()
