#!/usr/bin/env python3
"""Quick test to verify hw_limits.inc parser works correctly.

Expected values are derived from ``bios/src/hw_limits.inc`` at the time
this test was written.  If the include file changes, update the
assertions below.
"""

import traceback
import sys

from fcon import parse_hw_limits

# --- values expected from bios/src/hw_limits.inc ---
_EXPECTED_CLOCK_SPEED = 3_000_000
_EXPECTED_SCREEN_COLS = 40
_EXPECTED_SCREEN_ROWS = 24
_EXPECTED_SCREEN_SIZE = _EXPECTED_SCREEN_COLS * _EXPECTED_SCREEN_ROWS  # 960
_EXPECTED_START_CHAR_RAM = 0xD000
_EXPECTED_END_CHAR_RAM = _EXPECTED_START_CHAR_RAM + _EXPECTED_SCREEN_SIZE  # $D3C0
_EXPECTED_START_COLOR_RAM = 0xE000
_EXPECTED_END_COLOR_RAM = _EXPECTED_START_COLOR_RAM + _EXPECTED_SCREEN_SIZE  # $E3C0
_EXPECTED_DEFAULT_COLOR = 0x6F

# Test parsing the hardware limits file
hw = parse_hw_limits("bios/src/hw_limits.inc")

print("Parsed Hardware Limits:")
print(f"  CLOCK_SPEED: {hw.clock_speed}")
print(f"  SCREEN_COLS: {hw.screen_cols}")
print(f"  SCREEN_ROWS: {hw.screen_rows}")
print(f"  SCREEN_SIZE: {hw.screen_size} (expected: {_EXPECTED_SCREEN_SIZE})")
print(
    f"  START_REGION_CHAR_RAM: ${hw.start_region_char_ram:04X} (expected: ${_EXPECTED_START_CHAR_RAM:04X})"
)
print(
    f"  END_REGION_CHAR_RAM: ${hw.end_region_char_ram:04X} (expected: ${_EXPECTED_END_CHAR_RAM:04X})"
)
print(
    f"  START_REGION_COLOR_RAM: ${hw.start_region_color_ram:04X} (expected: ${_EXPECTED_START_COLOR_RAM:04X})"
)
print(
    f"  END_REGION_COLOR_RAM: ${hw.end_region_color_ram:04X} (expected: ${_EXPECTED_END_COLOR_RAM:04X})"
)
print(
    f"  DEFAULT_COLOR: ${hw.default_color:02X} (expected: ${_EXPECTED_DEFAULT_COLOR:02X})"
)

# Verify values
passed = 0
failed = 0


def _check(name: str, actual: int, expected: int) -> None:
    global passed, failed
    if actual == expected:
        passed += 1
    else:
        failed += 1
        print(f"  MISMATCH: {name}: got {actual}, expected {expected}")


_check("CLOCK_SPEED", hw.clock_speed, _EXPECTED_CLOCK_SPEED)
_check("SCREEN_COLS", hw.screen_cols, _EXPECTED_SCREEN_COLS)
_check("SCREEN_ROWS", hw.screen_rows, _EXPECTED_SCREEN_ROWS)
_check("SCREEN_SIZE", hw.screen_size, _EXPECTED_SCREEN_SIZE)
_check("START_REGION_CHAR_RAM", hw.start_region_char_ram, _EXPECTED_START_CHAR_RAM)
_check("END_REGION_CHAR_RAM", hw.end_region_char_ram, _EXPECTED_END_CHAR_RAM)
_check("START_REGION_COLOR_RAM", hw.start_region_color_ram, _EXPECTED_START_COLOR_RAM)
_check("END_REGION_COLOR_RAM", hw.end_region_color_ram, _EXPECTED_END_COLOR_RAM)
_check("DEFAULT_COLOR", hw.default_color, _EXPECTED_DEFAULT_COLOR)

# Second pass: verify the parser works when called programmatically
try:
    hw2 = parse_hw_limits("bios/src/hw_limits.inc")
    print("\n✓ Parser re-executed successfully!")
    print("\nHardware Configuration:")
    print(f"  Clock Speed: {hw2.clock_speed:,} Hz")
    print(
        f"  Screen Size: {hw2.screen_cols}x{hw2.screen_rows} ({hw2.screen_size} cells)"
    )
    print(
        f"  Char RAM: ${hw2.start_region_char_ram:04X}-${hw2.end_region_char_ram:04X}"
    )
    print(
        f"  Color RAM: ${hw2.start_region_color_ram:04X}-${hw2.end_region_color_ram:04X}"
    )
    print(f"  Default Color: ${hw2.default_color:02X}")
except Exception as e:
    print(f"\n✗ Error: {e}")
    traceback.print_exc()
    failed += 1

if failed:
    print(f"\n{failed} check(s) failed, {passed} passed.")
    sys.exit(1)
print(f"\nAll {passed} checks passed.")
