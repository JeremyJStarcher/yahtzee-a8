#!/usr/bin/env python3
"""
Fconsole - Official Emulator Start Script

Opens video output (vout) and debug output (dout) windows,
runs a simple 6502 emulator demo via py65 on the video display.
"""

import argparse
import math
import sys
import time
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pylib import video_display_pygame as pygame_vd
from pylib import video_display_text as text_vd
from pylib import video_display_tk as tk_vd

# ---------------------------------------------------------------------------
# Configuration data classes
# ---------------------------------------------------------------------------


@dataclass
class HardwareLimits:
    """Hardware configuration loaded from bios/src/hw_limits.inc"""

    clock_speed: int = 0
    screen_cols: int = 0
    screen_rows: int = 0
    screen_size: int = 0
    start_region_char_ram: int = 0
    end_region_char_ram: int = 0
    start_region_color_ram: int = 0
    end_region_color_ram: int = 0
    default_color: int = 0


@dataclass
class EmulatorConfig:
    """All runtime configuration, derived from CLI args and hardware limits."""

    # Display
    screen_cols: int
    screen_rows: int
    screen_scale: int
    video_backend: str
    text_font_family: str | None

    # CPU pacing
    instructions_per_batch: int
    clock_hz: float
    fallback_cycles_per_instruction: float
    max_catch_up_seconds: float
    host_yield_ms: int
    refresh_interval_ms: int

    # Memory layout (from hw_limits.inc)
    screen_size: int
    start_region_char_ram: int
    start_region_color_ram: int

    # BIOS
    bios_file: str = "bios/bios.bin"


# ---------------------------------------------------------------------------
# HW limits parser
# ---------------------------------------------------------------------------


def _eval_asm_expr(expr: str, variables: dict[str, int]) -> int:
    """Evaluate a simple assembly-style arithmetic expression.

    Supports decimal and ``$hex`` integer literals, ``'c'`` character
    literals, variable references, parentheses, and the operators
    ``+``, ``-``, ``*``, ``/`` (integer division, truncates toward
    zero).
    """
    _tokens: list[str] = []
    _pos = 0

    # -- tokenize -----------------------------------------------------------
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch.isspace():
            i += 1
            continue
        if ch in "+-*/()":
            _tokens.append(ch)
            i += 1
            continue
        if ch == "$":
            j = i + 1
            while j < len(expr) and expr[j] in "0123456789ABCDEFabcdef":
                j += 1
            if j == i + 1:
                raise ValueError(
                    f"expected hex digits after '$' at position {i} in {expr!r}"
                )
            _tokens.append(expr[i:j])
            i = j
            continue
        if ch == "'":
            j = i + 1
            if j >= len(expr):
                raise ValueError(
                    f"unterminated character literal at position {i} in {expr!r}"
                )
            # Allow backslash escape: '\n', '\\', '\'', etc.
            if expr[j] == "\\":
                j += 1
                if j >= len(expr):
                    raise ValueError(
                        f"unterminated escape in character literal at position {i} in {expr!r}"
                    )
                ch_val = _SIMPLE_ESCAPES.get(expr[j], ord(expr[j]))
            else:
                ch_val = ord(expr[j])
            j += 1
            if j >= len(expr) or expr[j] != "'":
                raise ValueError(
                    f"unterminated character literal at position {i} in {expr!r}"
                )
            _tokens.append(str(ch_val))
            i = j + 1
            continue
        if ch.isdigit():
            j = i
            while j < len(expr) and expr[j].isdigit():
                j += 1
            _tokens.append(expr[i:j])
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < len(expr) and (expr[j].isalnum() or expr[j] == "_"):
                j += 1
            _tokens.append(expr[i:j])
            i = j
            continue
        raise ValueError(f"unexpected character {ch!r} at position {i} in {expr!r}")

    # -- recursive-descent parser -------------------------------------------

    def _peek() -> str | None:
        nonlocal _pos
        return _tokens[_pos] if _pos < len(_tokens) else None

    def _advance() -> str:
        nonlocal _pos
        tok = _tokens[_pos]
        _pos += 1
        return tok

    def _expect(expected: str) -> None:
        tok = _peek()
        if tok != expected:
            raise ValueError(f"expected {expected!r}, got {tok!r} in {expr!r}")
        _advance()

    def _parse_expr() -> int:
        left = _parse_term()
        while (tok := _peek()) in ("+", "-"):
            _advance()
            right = _parse_term()
            if tok == "+":
                left += right
            else:
                left -= right
        return left

    def _parse_term() -> int:
        left = _parse_factor()
        while (tok := _peek()) in ("*", "/"):
            _advance()
            right = _parse_factor()
            if tok == "*":
                left *= right
            elif right == 0:
                raise ValueError(f"division by zero in {expr!r}")
            else:
                # Integer division truncating toward zero (Python // floors).
                left = int(left / right)
        return left

    def _parse_factor() -> int:
        tok = _peek()
        if tok is None:
            raise ValueError(f"unexpected end of expression in {expr!r}")
        if tok == "(":
            _advance()
            value = _parse_expr()
            _expect(")")
            return value
        if tok.startswith("$"):
            return int(_advance()[1:], 16)
        if tok.isdigit() or (tok.startswith("-") and tok[1:].isdigit()):
            # Handle negative integer literals (the tokenizer doesn't
            # capture leading '-', but we keep this for robustness).
            return int(_advance())
        if tok[0].isalpha() or tok[0] == "_":
            name = _advance()
            if name not in variables:
                raise ValueError(f"undefined variable {name!r} in {expr!r}")
            return variables[name]
        raise ValueError(f"unexpected token {tok!r} in {expr!r}")

    result = _parse_expr()
    if _pos != len(_tokens):
        raise ValueError(f"unexpected trailing tokens in {expr!r}: {_tokens[_pos:]!r}")
    return result


_SIMPLE_ESCAPES: dict[str, int] = {
    "n": ord("\n"),
    "r": ord("\r"),
    "t": ord("\t"),
    "\\": ord("\\"),
    "'": ord("'"),
    '"': ord('"'),
}


def parse_hw_limits(filepath: str) -> HardwareLimits:
    """
    Parse assembly include file with assignment expressions.

    Handles decimal, hex ($XX), arithmetic expressions, and character
    literals (``'c'``).  Uses a small recursive-descent evaluator so
    that only the expected expression grammar is accepted.
    """
    hw = HardwareLimits()

    # First pass: collect all assignments as raw strings
    assignments: dict[str, str] = {}
    with open(filepath) as f:
        for line_num, line in enumerate(f, 1):
            # Strip comments (everything after semicolon)
            if ";" in line:
                line = line[: line.index(";")]

            line = line.strip()
            if not line or "=" not in line:
                continue

            try:
                var_name, expr = line.split("=", 1)
                var_name = var_name.strip()
                expr = expr.strip()

                if not var_name or not expr:
                    continue

                assignments[var_name] = expr
            except Exception as e:
                print(f"Warning: Could not parse line {line_num}: {e}")

    # Map assembly variable names to HardwareLimits dataclass fields.
    _field_map: dict[str, tuple[str, type]] = {
        "CLOCK_SPEED": ("clock_speed", int),
        "SCREEN_COLS": ("screen_cols", int),
        "SCREEN_ROWS": ("screen_rows", int),
        "SCREEN_SIZE": ("screen_size", int),
        "START_REGION_CHAR_RAM": ("start_region_char_ram", int),
        "END_REGION_CHAR_RAM": ("end_region_char_ram", int),
        "START_REGION_COLOR_RAM": ("start_region_color_ram", int),
        "END_REGION_COLOR_RAM": ("end_region_color_ram", int),
        "DEFAULT_COLOR": ("default_color", int),
    }

    # Second pass: evaluate expressions using already-parsed variables
    evaluated: dict[str, int] = {}
    max_iterations = len(assignments) + 1  # Prevent infinite loops

    for _ in range(max_iterations):
        remaining: list[tuple[str, str]] = []
        made_progress = False

        for var_name, expr in assignments.items():
            if var_name in evaluated:
                continue

            try:
                value = _eval_asm_expr(expr, evaluated)
            except (ValueError, ZeroDivisionError) as exc:
                print(f"Warning: Could not evaluate {var_name!r}: {exc}")
                remaining.append((var_name, expr))
                continue

            evaluated[var_name] = value
            made_progress = True

            if var_name in _field_map:
                field_name, field_type = _field_map[var_name]
                setattr(hw, field_name, field_type(value))

        if not made_progress and remaining:
            print(f"Warning: Could not resolve dependencies for: {remaining}")
            break

        assignments = dict(remaining)

    return hw


# ---------------------------------------------------------------------------
# Argparse helpers
# ---------------------------------------------------------------------------


def positive_int(value: str) -> int:
    """Argparse converter accepting positive integers only."""
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def positive_float(value: str) -> float:
    """Argparse converter accepting positive floating-point values only."""
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def nonnegative_float(value: str) -> float:
    """Argparse converter accepting zero or a positive floating-point value."""
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value cannot be negative")
    return parsed


def parse_args() -> argparse.Namespace:
    """Parse emulator and clock-pacing options."""
    parser = argparse.ArgumentParser(
        description="Fconsole - Official Emulator Start Script"
    )
    parser.add_argument(
        "--instructions-per-batch",
        "--cycles-per-frame",
        dest="instructions_per_batch",
        type=positive_int,
        default=8000,
        help=(
            "Maximum instructions executed before checking the wall clock "
            "(default: 8000). --cycles-per-frame is retained as a legacy alias."
        ),
    )
    parser.add_argument(
        "--clock-hz",
        type=positive_float,
        default=None,  # Will be set from hw_limits.inc
        help="Target emulated CPU clock in Hz (overrides hw_limits.inc)",
    )
    parser.add_argument(
        "--fallback-cycles-per-instruction",
        type=positive_float,
        default=3.0,
        help=(
            "Approximate cycles per instruction if py65 lacks processorCycles "
            "(default: 3.0)"
        ),
    )
    parser.add_argument(
        "--max-catch-up-ms",
        type=nonnegative_float,
        default=100.0,
        help=(
            "Discard wall-clock lag beyond this amount instead of running a long "
            "100%% catch-up burst (default: 100)"
        ),
    )
    parser.add_argument(
        "--host-yield-ms",
        type=positive_int,
        default=1,
        help=(
            "Minimum delay between CPU batches, even when behind schedule (default: 1)"
        ),
    )
    parser.add_argument(
        "--refresh-hz",
        type=positive_float,
        default=60.0,
        help=(
            "Maximum display refresh rate in Hz, independent of CPU batching "
            "(default: 60)"
        ),
    )
    parser.add_argument(
        "--screen-scale",
        type=positive_int,
        default=2,
        help="Screen scaling factor (default: 2)",
    )
    parser.add_argument(
        "--video-backend",
        choices=("tk", "text", "pygame"),
        default="pygame",
        help=(
            "Video renderer: pygame window (default), Tk bitmap cells, or "
            "native Tk text cells"
        ),
    )
    parser.add_argument(
        "--text-font-family",
        default=None,
        help=("Optional font family for --video-backend text; defaults to TkFixedFont"),
    )
    parser.add_argument(
        "--load",
        dest="program_file",
        default=None,
        metavar="FILE",
        help=(
            "Binary program file to load into user space. Format: 2-byte little-endian "
            "load address, 2-byte little-endian start-function pointer (stored at "
            "$0203/$0204), followed by the program bytes copied into RAM."
        ),
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace, hw: HardwareLimits) -> EmulatorConfig:
    """Merge CLI arguments and hardware limits into a single config object."""
    clock_hz = args.clock_hz if args.clock_hz else float(hw.clock_speed)
    refresh_interval_ms = max(1, round(1000.0 / args.refresh_hz))

    return EmulatorConfig(
        screen_cols=hw.screen_cols,
        screen_rows=hw.screen_rows,
        screen_scale=args.screen_scale,
        video_backend=args.video_backend,
        text_font_family=args.text_font_family,
        instructions_per_batch=args.instructions_per_batch,
        clock_hz=clock_hz,
        fallback_cycles_per_instruction=args.fallback_cycles_per_instruction,
        max_catch_up_seconds=args.max_catch_up_ms / 1000.0,
        host_yield_ms=args.host_yield_ms,
        refresh_interval_ms=refresh_interval_ms,
        screen_size=hw.screen_size,
        start_region_char_ram=hw.start_region_char_ram,
        start_region_color_ram=hw.start_region_color_ram,
    )


# ---------------------------------------------------------------------------
# Emulator core
# ---------------------------------------------------------------------------


@dataclass
class MemoryRange:
    start: int
    end: int = -1
    length: int = -1
    read_cb: Callable[[int], int] | None = None
    write_cb: Callable[[int, int], None] | None = None

    def __post_init__(self) -> None:
        if self.end == -1 and self.length == -1:
            raise ValueError("Range error: end and length cannot both be empty")
        if self.end == -1:
            self.end = self.start + self.length - 1
        elif self.length == -1:
            self.length = self.end - self.start + 1

    def contains(self, address: int) -> bool:
        """Check if an address falls within this memory range."""
        return self.start <= address <= self.end


class SystemBus:
    """Custom system bus dispatching memory reads and writes across
    configured ranges."""

    # Keyboard status addresses (memory-mapped I/O)
    KB_ASCII_ADDR = 0x0200
    KB_FLAGS_ADDR = 0x0201
    # $0202 holds $4C (JMP) if a program is loaded
    FLAG_ROM_LOADED = 0x0202
    ROM_LOADED_PTR_L = 0x0203
    ROM_LOADED_PTR_H = 0x0204

    # Keyboard flag bits
    KB_FLAG_SHIFT = 0x01
    KB_FLAG_CTRL = 0x02

    def __init__(
        self,
        config: EmulatorConfig,
        char_write_cb: Callable[[int, int], None] | None = None,
        color_write_cb: Callable[[int, int], None] | None = None,
        key_event_cb: Callable[[int, int], None] | None = None,
    ) -> None:
        self.char_write_cb = char_write_cb
        self.color_write_cb = color_write_cb
        self.key_event_cb = key_event_cb

        # Keyboard state (memory-mapped I/O at $0200-$0201)
        self._kb_ascii: int = 0x00
        self._kb_flags: int = 0x00

        self.ram = bytearray(0x8000)  # 32KB RAM ($0000-$7FFF)
        self.rom = bytearray(0x3000)  # 4KB BIOS ROM ($F000-$FFFF)

        # Local VRAM buffers; writes are forwarded to the display callbacks.
        self._fallback_char_ram = bytearray(config.screen_size)
        self._fallback_color_ram = bytearray(config.screen_size)

        # Load BIOS binary into ROM if available
        try:
            with open(config.bios_file, "rb") as f:
                bios_data = f.read()
                copy_size = min(len(bios_data), len(self.rom))
                self.rom[:copy_size] = bios_data[:copy_size]
                print(
                    f"Loaded BIOS: {config.bios_file} "
                    f"({len(bios_data)} 0x{len(bios_data):04X} bytes)"
                )
        except FileNotFoundError:
            print(f"WARNING: BIOS file not found: {config.bios_file}")
        except Exception as e:
            print(f"ERROR loading BIOS: {e}")

        # Dynamic memory map table
        self.bus_map: list[MemoryRange] = [
            MemoryRange(
                start=0x0000,
                length=config.start_region_char_ram,
                read_cb=lambda offset: self.ram[offset],
                write_cb=self._write_ram,
            ),
            MemoryRange(
                start=config.start_region_char_ram,
                length=config.screen_size,
                read_cb=self._read_char_mem,
                write_cb=self._write_char_mem,
            ),
            MemoryRange(
                start=config.start_region_color_ram,
                length=config.screen_size,
                read_cb=self._read_color_mem,
                write_cb=self._write_color_mem,
            ),
            MemoryRange(
                start=0xD000,
                end=0xFFFF,
                read_cb=lambda offset: self.rom[offset],
            ),
        ]

    # -- RAM ----------------------------------------------------------------

    def _write_ram(self, offset: int, value: int) -> None:
        self.ram[offset] = value & 0xFF

    # -- Character memory ---------------------------------------------------

    def _read_char_mem(self, offset: int) -> int:
        return self._fallback_char_ram[offset]

    def _write_char_mem(self, offset: int, value: int) -> None:
        val = value & 0xFF
        if self._fallback_char_ram[offset] == val:
            return
        self._fallback_char_ram[offset] = val
        if self.char_write_cb:
            self.char_write_cb(offset, val)

    # -- Color memory -------------------------------------------------------

    def _read_color_mem(self, offset: int) -> int:
        return self._fallback_color_ram[offset]

    def _write_color_mem(self, offset: int, value: int) -> None:
        val = value & 0xFF
        if self._fallback_color_ram[offset] == val:
            return
        self._fallback_color_ram[offset] = val
        if self.color_write_cb:
            self.color_write_cb(offset, val)

    # -- Keyboard I/O -------------------------------------------------------

    def _read_kb_ascii(self, offset: int) -> int:
        """Read the ASCII value of the last key pressed."""
        return self._kb_ascii

    def _write_kb_ascii(self, offset: int, value: int) -> None:
        """Write to keyboard ASCII register (clears pending key)."""
        self._kb_ascii = 0x00
        if self.key_event_cb:
            self.key_event_cb(0x00, 0x00)

    def _read_kb_flags(self, offset: int) -> int:
        """Read keyboard modifier flags."""
        return self._kb_flags

    def _write_kb_flags(self, offset: int, value: int) -> None:
        """Ignore CPU writes to the keyboard flags register.

        The modifier flags are host-controlled (set via
        ``update_key_state``); they are read-only from the CPU's
        perspective.
        """
        return

    def update_key_state(self, ascii_val: int, flags: int) -> None:
        """Update keyboard state from external event source."""
        self._kb_ascii = ascii_val & 0xFF
        self._kb_flags = flags & 0xFF

    # -- Bus protocol -------------------------------------------------------

    def __getitem__(self, address: int) -> int:
        # Keyboard memory-mapped I/O takes priority over the general bus
        # map.  Otherwise the broad RAM range ($0000+) would shadow the
        # keyboard registers at $0200-$0201 and the BIOS could never read
        # an incoming keystroke.
        if address == self.KB_ASCII_ADDR:
            return self._read_kb_ascii(0)
        if address == self.KB_FLAGS_ADDR:
            return self._read_kb_flags(0)

        for m_range in self.bus_map:
            if m_range.contains(address):
                offset = address - m_range.start
                if m_range.read_cb:
                    return m_range.read_cb(offset)
                break

        # Unmapped space returns NOP instruction ($EA)
        return 0xEA

    def __setitem__(self, address: int, value: int) -> None:
        # Keyboard memory-mapped I/O takes priority over the general bus
        # map (see __getitem__), so the BIOS "STA $0200" handshake can
        # clear the pending keystroke instead of being swallowed by RAM.
        if address == self.KB_ASCII_ADDR:
            self._write_kb_ascii(0, value)
            return
        if address == self.KB_FLAGS_ADDR:
            self._write_kb_flags(0, value)
            return

        for m_range in self.bus_map:
            if m_range.contains(address):
                if m_range.write_cb:
                    offset = address - m_range.start
                    m_range.write_cb(offset, value)
                return


class Cpu6502Module:
    """Simple wrapper for the py65 6502 emulator."""

    def __init__(
        self,
        config: EmulatorConfig,
        mpu_class: type,
        char_write_cb: Callable[[int, int], None] | None = None,
        color_write_cb: Callable[[int, int], None] | None = None,
        key_event_cb: Callable[[int, int], None] | None = None,
    ) -> None:
        self._fallback_cycles_per_instruction = config.fallback_cycles_per_instruction

        self.bus = SystemBus(
            config,
            char_write_cb=char_write_cb,
            color_write_cb=color_write_cb,
            key_event_cb=key_event_cb,
        )

        reset_vector_address = 0xFFFC
        reset_vector = self.bus[reset_vector_address] + (
            self.bus[reset_vector_address + 1] * 256
        )
        self.cpu = mpu_class(memory=self.bus, pc=reset_vector)

    def step(self) -> float:
        """Execute one instruction and return the cycles it consumed."""
        cycles_before = getattr(self.cpu, "processorCycles", None)
        self.cpu.step()
        cycles_after = getattr(self.cpu, "processorCycles", None)

        if cycles_before is not None and cycles_after is not None:
            elapsed_cycles = cycles_after - cycles_before
            if elapsed_cycles > 0:
                return float(elapsed_cycles)

        return self._fallback_cycles_per_instruction

    @property
    def has_native_cycle_counter(self) -> bool:
        """Return whether this py65 MPU exposes its accumulated cycle
        count."""
        return hasattr(self.cpu, "processorCycles")

    def load_program(self, filepath: str) -> None:
        """Load a binary program into RAM.

        File format (little-endian):
          bytes 0-1 : 16-bit address where the program is loaded
          bytes 2-3 : 16-bit pointer to the start function, stored in
                      SystemBus RAM at ROM_LOADED_PTR_L/$0203 and
                      ROM_LOADED_PTR_H/$0204
          bytes 4+  : program bytes copied into RAM starting at the
                      load address

        Raises SystemExit on a missing file or a file too short to hold
        the 4-byte header.
        """
        bus = self.bus
        try:
            with open(filepath, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            print(f"ERROR: Program file not found: {filepath}")
            sys.exit(1)
        except OSError as e:
            print(f"ERROR: Cannot read program file {filepath}: {e}")
            sys.exit(1)

        if len(data) < 4:
            print(
                f"ERROR: Program file too short ({len(data)} bytes); "
                "need at least 4 bytes (2-byte load address + 2-byte start pointer)"
            )
            sys.exit(1)

        load_addr = int.from_bytes(data[0:2], "little")
        start_ptr = int.from_bytes(data[2:4], "little")
        program_bytes = data[4:]

        bus.ram[bus.FLAG_ROM_LOADED] = 0x4C  # JMP instruction
        bus.ram[bus.ROM_LOADED_PTR_L] = start_ptr & 0xFF
        bus.ram[bus.ROM_LOADED_PTR_H] = (start_ptr >> 8) & 0xFF
        bus.ram[load_addr : load_addr + len(program_bytes)] = program_bytes

        print(f"Loaded program: {filepath}")
        print(f"  Load address   : ${load_addr:04X}")
        print(f"  Start function : ${start_ptr:04X}")
        print(f"  Program bytes  : {len(program_bytes)}")
        print(
            f"  Start pointer  : $0203=${bus.ram[bus.ROM_LOADED_PTR_L]:02X} "
            f"$0204=${bus.ram[bus.ROM_LOADED_PTR_H]:02X}"
        )


class FConsole:
    """Main emulator controller managing both output windows."""

    def __init__(self, config: EmulatorConfig, mpu_class: type) -> None:
        self.config = config
        self.running = True
        self.isDirty = True

        # Coalesce repeated writes to the same cell.
        self._pending_char_writes: dict[int, int] = {}
        self._pending_color_writes: dict[int, int] = {}

        # Create windows
        self._create_video_window()
        self._create_debug_window()

        # Send test message directly to the dout text window
        self.console_print("Hello World!")

        # Initialize 6502 module with write-only display callbacks.
        # Reads are handled entirely within the bus's local VRAM buffers.
        self.cpu_module = Cpu6502Module(
            config,
            mpu_class,
            char_write_cb=self._on_char_memory_write,
            color_write_cb=self._on_color_memory_write,
            key_event_cb=self._on_key_event,
        )

        # Pacing state
        self._emulated_cycles = 0.0
        self._clock_origin = time.perf_counter()

    def _create_video_window(self) -> None:
        """Create the primary video output window."""
        print("Opening video output window (vout)...")

        cfg = self.config
        if cfg.video_backend == "text":
            self.vout = text_vd.Video(  # pyrefly: ignore[bad-assignment]
                rows=cfg.screen_rows,
                columns=cfg.screen_cols,
                scale=cfg.screen_scale,
                font_family=cfg.text_font_family,
            )
            print(
                "Text renderer: "
                f"font={self.vout.font_family!r}, "
                f"cell={self.vout.cell_width}x{self.vout.cell_height}px"
            )
        elif cfg.video_backend == "pygame":
            try:
                self.vout = pygame_vd.Video(  # pyrefly: ignore[bad-assignment]
                    rows=cfg.screen_rows,
                    columns=cfg.screen_cols,
                    scale=cfg.screen_scale,
                )
            except ImportError as e:
                print("ERROR: The 'pygame' backend requires the pygame package.")
                print("Install it with: pip install pygame")
                print(f"  (underlying error: {e})")
                sys.exit(1)
        else:
            self.vout = tk_vd.Video(  # pyrefly: ignore[bad-assignment]
                rows=cfg.screen_rows,
                columns=cfg.screen_cols,
                scale=cfg.screen_scale,
            )
        self.vout.set_title("fcon - vout")
        self.vout.set_close_handler(self._on_close)
        self.vout.set_key_callback(self._on_key_event)

    def _create_debug_window(self) -> None:
        """Create the debug output text window."""
        print("Opening debug output window (dout)...")

        if self.config.video_backend == "pygame":
            # Pygame backend has no Tk root to attach to; use a standalone
            # window and pump it from the pygame main loop.
            self.dout_root = tk.Tk()
        else:
            self.dout_root = tk.Toplevel(  # pyrefly: ignore[bad-assignment]
                self.vout._root
            )
        self.dout_root.title("fcon - dout")
        self.dout_root.geometry("600x400")
        self.dout_root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.debug_text = tk.Text(
            self.dout_root,
            wrap=tk.WORD,
            bg="black",
            fg="#00FF00",
            insertbackground="#00FF00",
        )
        self.debug_text.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

    def console_print(self, text: str) -> None:
        """Write text directly into the debug window (dout)."""
        if hasattr(self, "debug_text") and self.debug_text:
            self.debug_text.insert(tk.END, str(text) + "\n")
            self.debug_text.see(tk.END)

    # -- Video memory write callbacks ---------------------------------------

    def _on_char_memory_write(self, offset: int, value: int) -> None:
        """Queue a character-cell update for the next video frame."""
        self._pending_char_writes[offset] = value
        self.isDirty = True

    def _on_color_memory_write(self, offset: int, value: int) -> None:
        """Queue a color-cell update for the next video frame."""
        self._pending_color_writes[offset] = value
        self.isDirty = True

    # -- Keyboard input ------------------------------------------------------

    def _on_key_event(self, ascii_val: int, flags: int) -> None:
        """Handle keyboard event from video backend.

        Updates the SystemBus keyboard registers so the 6502 program can
        read the ASCII value at $0200 and modifier flags at $0201.
        """
        self.cpu_module.bus.update_key_state(ascii_val, flags)

    # -- CPU state formatting -----------------------------------------------

    @staticmethod
    def _format_cpu_state(cpu: object, bus: object) -> str:
        """Format the 6502 register state as a human-readable string."""
        p = cpu.p  # type: ignore[attr-defined]
        return (
            f"{cpu.a:02X} "  # type: ignore[attr-defined]
            f"{cpu.x:02X} "  # type: ignore[attr-defined]
            f"{cpu.y:02X} "  # type: ignore[attr-defined]
            f"{cpu.sp:02X} "  # type: ignore[attr-defined]
            f"{(p >> 7) & 1}"
            f"{(p >> 6) & 1}"
            f"{(p >> 5) & 1}"
            f"-"
            f"{(p >> 3) & 1}"
            f"{(p >> 2) & 1}"
            f"{(p >> 1) & 1}"
            f"{p & 1}"
            f" {bus[0xFFFD]:02X}"
            f"{bus[0xFFFC]:02X}"
        )

    def _log_cpu_state_to_console(self) -> None:
        """Log current 6502 register state to the debug console."""
        output_lines = [
            " A  X  Y SP NV-BDIZC Vector",
            "---------------------",
            self._format_cpu_state(self.cpu_module.cpu, self.cpu_module.bus),
            "",
        ]
        output = "\n".join(output_lines)
        self.console_print(output)
        print(output)

    # -- Frame / step loops -------------------------------------------------

    def _update_video_frame(self) -> None:
        """Flush coalesced VRAM writes and redraw at a bounded frame rate."""
        if not self.running:
            return

        if self.isDirty:
            for offset, value in self._pending_char_writes.items():
                self.vout.set_screen(offset, value)
            for offset, value in self._pending_color_writes.items():
                self.vout.set_color(offset, value)

            self._pending_char_writes.clear()
            self._pending_color_writes.clear()
            self.vout.refresh_screen()
            self.isDirty = False

        self.vout.schedule(self.config.refresh_interval_ms, self._update_video_frame)

    def _update_cpu_step(self) -> None:
        """Execute one batch, then schedule the next batch at CPU-clock
        speed."""
        cfg = self.config
        batch_cycles = 0.0

        for _ in range(cfg.instructions_per_batch):
            batch_cycles += self.cpu_module.step()

            n = self.cpu_module.bus[self.cpu_module.cpu.pc]
            if n == 0x00:  # Break instruction
                self._log_cpu_state_to_console()

        self._emulated_cycles += batch_cycles

        if not self.running:
            return

        now = time.perf_counter()
        target_time = self._clock_origin + (self._emulated_cycles / cfg.clock_hz)
        lag_seconds = now - target_time

        if lag_seconds > cfg.max_catch_up_seconds:
            self._clock_origin = now - (self._emulated_cycles / cfg.clock_hz)
            target_time = now

        ahead_seconds = max(0.0, target_time - now)
        clock_delay_ms = math.ceil((ahead_seconds * 1000.0) - 1e-9)
        delay_ms = max(cfg.host_yield_ms, clock_delay_ms)
        self.vout.schedule(delay_ms, self._update_cpu_step)

    def _on_close(self) -> None:
        """Handle vout window close."""
        self.running = False
        try:
            self.vout.close()
            self.dout_root.destroy()
        except Exception:
            pass

    def run(self) -> None:
        """Start the main emulator loop."""
        cfg = self.config
        print("=" * 60)
        print("FCONSOLE EMULATOR")
        print("=" * 60)
        print(f"Video: {cfg.screen_rows} rows x {cfg.screen_cols} columns")
        print("Mode : py65 6502 (memory mapped bus table active)")
        print(f"Video: {cfg.video_backend} backend")
        if cfg.video_backend == "text":
            print("Copy : drag to select, Ctrl+C to copy; Ctrl+A selects all")
        cycle_mode = (
            "py65 processorCycles"
            if self.cpu_module.has_native_cycle_counter
            else (
                f"fallback ({cfg.fallback_cycles_per_instruction:g} cycles/instruction)"
            )
        )
        print(f"Clock: {cfg.clock_hz:g} Hz; timing source: {cycle_mode}")
        print("\nClose either window to exit.\n")

        self._update_cpu_step()
        self._update_video_frame()

        try:
            if cfg.video_backend == "pygame":
                self._run_pygame_mainloop()
            else:
                self.vout.mainloop()
        except tk.TclError:
            pass
        finally:
            if self.running:
                self._on_close()

    def _run_pygame_mainloop(self) -> None:
        """Drive the pygame window and the standalone debug Tk window.

        Pygame has no ``after``/``mainloop`` of its own.  This loop pumps
        the video output's events and due scheduled callbacks while keeping
        the debug window responsive by pumping its Tk event queue as well.
        """
        while self.running:
            self.vout.pump()
            try:
                self.dout_root.update()
            except tk.TclError:
                break
            time.sleep(0.001)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for fconsole emulator."""
    args = parse_args()

    hw_config_path = Path("bios/src/hw_limits.inc")
    if not hw_config_path.exists():
        print(f"ERROR: Hardware limits file not found: {hw_config_path}")
        sys.exit(1)

    hw_config = parse_hw_limits(str(hw_config_path))
    config = build_config(args, hw_config)

    print(
        "Config: "
        f"clock_hz={config.clock_hz:g} ({hw_config.clock_speed}), "
        f"instructions_per_batch={config.instructions_per_batch}, "
        f"fallback_cycles_per_instruction="
        f"{config.fallback_cycles_per_instruction:g}, "
        f"max_catch_up_ms={config.max_catch_up_seconds * 1000:g}, "
        f"host_yield_ms={config.host_yield_ms}, "
        f"screen_scale={config.screen_scale}, "
        f"refresh_hz={1000.0 / config.refresh_interval_ms:g}, "
        f"screen_size={config.screen_cols}x{config.screen_rows}, "
        f"video_backend={config.video_backend}, "
        f"text_font_family={config.text_font_family!r}"
    )

    # py65 is imported lazily so that parse_hw_limits can be tested without it.
    try:
        from py65.devices.mpu6502 import MPU  # pyrefly: ignore[missing-import]
    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        print("Please install py65: pip install py65")
        sys.exit(1)

    console = FConsole(config, MPU)

    # Load a user program into RAM, if one was provided.
    if args.program_file:
        console.cpu_module.load_program(args.program_file)

    console.run()
    sys.exit(0)


if __name__ == "__main__":
    main()
