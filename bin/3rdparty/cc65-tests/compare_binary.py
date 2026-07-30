#!/usr/bin/env python3
"""compare_binary.py — Cross-platform byte-for-byte file comparator.

Usage:
    python3 tests/compare_binary.py <file1> <file2>

Reports file sizes, first differing offset with a hex dump window,
and exits with status 0 on match, 1 on mismatch.
"""

import sys
from pathlib import Path


def _hex_window(data: bytes, offset: int, radius: int = 16) -> str:
    """Return a hex dump of bytes around `offset`."""
    start = max(0, offset - radius)
    end = min(len(data), offset + radius)
    lines: list[str] = []
    for pos in range(start, end, 16):
        chunk = data[pos : pos + 16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        marker = ""
        if pos <= offset < pos + 16:
            col = (offset - pos) * 3
            marker = "\n" + " " * (10 + col) + "^"
        lines.append(f"  {pos:08X}  {hex_part:<48s} {ascii_part}{marker}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"Usage: {argv[0]} <file1> <file2>", file=sys.stderr)
        return 2

    path_a = Path(argv[1])
    path_b = Path(argv[2])

    for p in (path_a, path_b):
        if not p.is_file():
            print(f"ERROR: File not found: {p}", file=sys.stderr)
            return 2

    data_a = path_a.read_bytes()
    data_b = path_b.read_bytes()

    print(f"A: {path_a}  ({len(data_a)} bytes)")
    print(f"B: {path_b}  ({len(data_b)} bytes)")

    if len(data_a) != len(data_b):
        print(f"FAIL: Size mismatch ({len(data_a)} != {len(data_b)})")
        return 1

    for i, (ba, bb) in enumerate(zip(data_a, data_b)):
        if ba != bb:
            print(f"FAIL: First difference at offset {i} (0x{i:X})")
            print(f"  A[{i}] = 0x{ba:02X}  B[{i}] = 0x{bb:02X}")
            print()
            print("Context (file A):")
            print(_hex_window(data_a, i))
            print()
            print("Context (file B):")
            print(_hex_window(data_b, i))
            return 1

    print("PASS: Files are identical.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
