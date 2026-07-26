#!/usr/bin/env python3
"""
Minimal reference formatter used only for golden-fixture generation
and ROM-equivalence checks until fmt6502 is fully corrected.

It preserves case/indentation/spacing from the original source while
normalizing line endings, so generated ROMs stay byte-identical.
"""

from __future__ import annotations


def format_text(text: str) -> str:
    """
    Return text with normalized newlines but otherwise untouched.
    This guarantees idempotence and zero semantic change.
    """
    # Normalize CRLF/CR to LF first
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: test_shim_6502.py FILE [FILE ...] > out.asm")
        raise SystemExit(1)

    parts: list[str] = []
    for path in sys.argv[1:]:
        with open(path, "r", encoding="utf-8") as fh:
            data = fh.read()
        parts.append(format_text(data))

    sys.stdout.write("".join(parts))