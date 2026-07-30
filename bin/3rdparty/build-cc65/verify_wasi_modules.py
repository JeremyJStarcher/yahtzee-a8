#!/usr/bin/env python3
"""verify_wasi_modules.py — Validate WASI command-module import/export contract.

For each .wasm file given on the command line, verify:
  - exports _start
  - host imports come exclusively from wasi_snapshot_preview1
  - does NOT import from env, js, emscripten, or any unknown module

Uses only the standard library (no external dependencies) by parsing the
WebAssembly binary format directly.

Usage:
    python3 build/verify_wasi_modules.py bin/wasi/*.wasm
"""

import struct
import sys
from pathlib import Path


# --- WebAssembly binary-format constants ---
MAGIC = b"\x00asm"
VERSION = b"\x01\x00\x00\x00"

SECTION_TYPE_CUSTOM = 0
SECTION_TYPE_TYPE = 1
SECTION_TYPE_IMPORT = 2
SECTION_TYPE_FUNCTION = 3
SECTION_TYPE_TABLE = 4
SECTION_TYPE_MEMORY = 5
SECTION_TYPE_GLOBAL = 6
SECTION_TYPE_EXPORT = 7
SECTION_TYPE_START = 8
SECTION_TYPE_ELEMENT = 9
SECTION_TYPE_CODE = 10
SECTION_TYPE_DATA = 11

# External kinds for import/export sections
EXT_FUNCTION = 0
EXT_TABLE = 1
EXT_MEMORY = 2
EXT_GLOBAL = 3

IMPORT_KIND_NAMES = {
    EXT_FUNCTION: "function",
    EXT_TABLE: "table",
    EXT_MEMORY: "memory",
    EXT_GLOBAL: "global",
}

ALLOWED_IMPORT_MODULE = "wasi_snapshot_preview1"
REJECTED_IMPORT_MODULES = {"env", "js", "emscripten", "wasi_unstable"}


class WasmParseError(Exception):
    """Raised when the .wasm file cannot be parsed."""


def read_uleb128(data: bytes, offset: int) -> tuple[int, int]:
    """Read an unsigned LEB128 integer; return (value, new_offset)."""
    result = 0
    shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
    return result, offset


def read_name(data: bytes, offset: int) -> tuple[str, int]:
    """Read a length-prefixed UTF-8 name; return (name, new_offset)."""
    length, offset = read_uleb128(data, offset)
    name = data[offset : offset + length].decode("utf-8", errors="replace")
    return name, offset + length


def parse_import_section(data: bytes, offset: int) -> list[tuple[str, str, int]]:
    """Parse the import section; return list of (module, field, kind)."""
    count, offset = read_uleb128(data, offset)
    imports: list[tuple[str, str, int]] = []
    for _ in range(count):
        module, offset = read_name(data, offset)
        field, offset = read_name(data, offset)
        kind, offset = read_uleb128(data, offset)
        # Skip the type index (or table/memory/global type) — we only
        # care about the module/field names and the import kind.
        if kind == EXT_FUNCTION:
            _, offset = read_uleb128(data, offset)  # type index
        elif kind == EXT_TABLE:
            # elemtype (1 byte) + limits (flags + initial [+ max])
            offset += 1  # elemtype
            flags, offset = read_uleb128(data, offset)
            _, offset = read_uleb128(data, offset)  # initial
            if flags & 1:
                _, offset = read_uleb128(data, offset)  # max
        elif kind == EXT_MEMORY:
            flags, offset = read_uleb128(data, offset)
            _, offset = read_uleb128(data, offset)  # initial
            if flags & 1:
                _, offset = read_uleb128(data, offset)  # max
        elif kind == EXT_GLOBAL:
            offset += 1  # valtype
            offset += 1  # mutability
        imports.append((module, field, kind))
    return imports


def parse_export_section(data: bytes, offset: int) -> list[tuple[str, int]]:
    """Parse the export section; return list of (name, kind)."""
    count, offset = read_uleb128(data, offset)
    exports: list[tuple[str, int]] = []
    for _ in range(count):
        name, offset = read_name(data, offset)
        kind, offset = read_uleb128(data, offset)
        _, offset = read_uleb128(data, offset)  # index
        exports.append((name, kind))
    return exports


def validate_module(path: Path) -> list[str]:
    """Validate one .wasm module; return list of error strings (empty = pass)."""
    errors: list[str] = []

    try:
        data = path.read_bytes()
    except OSError as exc:
        return [f"Cannot read file: {exc}"]

    if len(data) < 8 or data[:4] != MAGIC or data[4:8] != VERSION:
        return ["Not a valid WebAssembly binary (bad magic/version)."]

    pos = 8
    exports: list[tuple[str, int]] = []
    imports: list[tuple[str, str, int]] = []

    while pos < len(data):
        section_id, pos = read_uleb128(data, pos)
        section_size, pos = read_uleb128(data, pos)
        section_end = pos + section_size

        if section_id == SECTION_TYPE_IMPORT:
            imports = parse_import_section(data, pos)
        elif section_id == SECTION_TYPE_EXPORT:
            exports = parse_export_section(data, pos)

        pos = section_end

    # --- contract checks ---

    # 1. Must export _start
    if ("_start", EXT_FUNCTION) not in exports:
        errors.append("Missing required export: _start (function)")

    # 2. All host imports must come from wasi_snapshot_preview1
    for module, field, kind in imports:
        kind_name = IMPORT_KIND_NAMES.get(kind, f"kind {kind}")
        if module in REJECTED_IMPORT_MODULES:
            errors.append(
                f"Rejected import from '{module}': {field} ({kind_name})"
            )
        elif module != ALLOWED_IMPORT_MODULE:
            errors.append(
                f"Unknown import module '{module}': {field} ({kind_name}) — "
                f"only '{ALLOWED_IMPORT_MODULE}' is allowed"
            )

    return errors


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(f"Usage: {argv[0]} <module.wasm>...", file=sys.stderr)
        return 2

    all_ok = True
    for arg in argv[1:]:
        path = Path(arg)
        errors = validate_module(path)
        if errors:
            all_ok = False
            print(f"FAIL  {path.name}")
            for err in errors:
                print(f"      {err}")
        else:
            print(f"PASS  {path.name}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
