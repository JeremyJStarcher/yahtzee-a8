#!/usr/bin/env python3
"""
Fconsole - Official Emulator Start Script

Opens video output (vout) and debug output (dout) windows,
runs a simple 6502 emulator demo via py65 on the video display.
"""

import argparse
import math
import re
import sys
import time
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pylib import video_display as bitmap_vd
from pylib import video_display_text as text_vd


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
    default_screen_char: str = " "


def parse_hw_limits(filepath: str) -> HardwareLimits:
    """
    Parse assembly include file with assignment expressions.

    Handles decimal, hex ($XX), arithmetic expressions, and character literals.
    Uses eval() safely since this is an internal trusted file.
    """
    hw = HardwareLimits()

    # First pass: collect all assignments as raw strings
    assignments = {}
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

    # Second pass: evaluate expressions using already-parsed variables
    evaluated = {}
    max_iterations = len(assignments) + 1  # Prevent infinite loops

    for _ in range(max_iterations):
        remaining = []
        made_progress = False

        for var_name, expr in assignments.items():
            if var_name in evaluated:
                continue

            # Convert assembly syntax to Python
            expr_py = expr

            # Replace $hex notation with 0xhex
            expr_py = re.sub(r"\$([0-9A-Fa-f]+)", r"0x\1", expr_py)

            # Handle character literals like ' ' -> chr(32) so eval keeps them as strings
            def replace_char_literal(match):
                return f"chr({ord(match.group(1))})"

            expr_py = re.sub(r"'(.?)'", replace_char_literal, expr_py)

            try:
                value = eval(expr_py, {}, evaluated)
                evaluated[var_name] = value
                made_progress = True

                # Map to dataclass fields
                field_mapping = {
                    "CLOCK_SPEED": ("clock_speed", int),
                    "SCREEN_COLS": ("screen_cols", int),
                    "SCREEN_ROWS": ("screen_rows", int),
                    "SCREEN_SIZE": ("screen_size", int),
                    "START_REGION_CHAR_RAM": ("start_region_char_ram", int),
                    "END_REGION_CHAR_RAM": ("end_region_char_ram", int),
                    "START_REGION_COLOR_RAM": ("start_region_color_ram", int),
                    "END_REGION_COLOR_RAM": ("end_region_color_ram", int),
                    "DEFAULT_COLOR": ("default_color", int),
                    "DEFAULT_SCREEN_CHAR": ("default_screen_char", str),
                }

                if var_name in field_mapping:
                    field_name, field_type = field_mapping[var_name]
                    setattr(hw, field_name, field_type(value))

            except Exception:
                remaining.append((var_name, expr))

        if not made_progress and remaining:
            print(f"Warning: Could not resolve dependencies for: {remaining}")
            break

        assignments = dict(remaining)

    return hw


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


def parse_args():
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
        choices=("bitmap", "text"),
        default="bitmap",
        help=(
            "Video renderer: authentic embedded-font bitmap output or native "
            "Tk text cells (default: bitmap)"
        ),
    )
    parser.add_argument(
        "--text-font-family",
        default=None,
        help=("Optional font family for --video-backend text; defaults to TkFixedFont"),
    )
    return parser.parse_args()


args = parse_args()

try:
    from py65.devices.mpu6502 import MPU  # pyrefly: ignore[missing-import]
except ImportError as e:
    print(f"ERROR: Missing dependency: {e}")
    print("Please install py65: pip install py65")
    sys.exit(1)


# Load hardware limits from assembly include file
hw_config_path = Path("bios/src/hw_limits.inc")
if not hw_config_path.exists():
    print(f"ERROR: Hardware limits file not found: {hw_config_path}")
    sys.exit(1)

hw_config = parse_hw_limits(str(hw_config_path))


# Set defaults from hardware config if not overridden by CLI args
INSTRUCTIONS_PER_BATCH = args.instructions_per_batch
CPU_CLOCK_HZ = args.clock_hz if args.clock_hz else float(hw_config.clock_speed)
FALLBACK_CYCLES_PER_INSTRUCTION = args.fallback_cycles_per_instruction
MAX_CATCH_UP_SECONDS = args.max_catch_up_ms / 1000.0
HOST_YIELD_MS = args.host_yield_ms
REFRESH_HZ = args.refresh_hz
REFRESH_INTERVAL_MS = max(1, round(1000.0 / REFRESH_HZ))
BIOS_FILE = "bios/bios.bin"
SCREEN_COLS = hw_config.screen_cols
SCREEN_ROWS = hw_config.screen_rows
SCREEN_SCALE = args.screen_scale
VIDEO_BACKEND = args.video_backend
TEXT_FONT_FAMILY = args.text_font_family
VID_DEBUG = False


@dataclass
class MemoryRange:
    name: str
    start: int
    end: int = -1
    len: int = -1
    read_cb: Callable[[int], int] | None = None
    write_cb: Callable[[int, int], None] | None = None
    default_read_val: int | None = None

    def __post_init__(self):
        if self.end == -1 and self.len == -1:
            raise ValueError("Range error: end and length cannot both be empty")

        if self.end == -1:
            self.end = self.start + self.len - 1

        if self.len == -1:
            self.len = self.end - self.start + 1

    def contains(self, address: int) -> bool:
        """Check if an address falls within this memory range."""
        return self.start <= address <= self.end


class SystemBus:
    """
    Custom system bus dispatching memory reads and writes across configured ranges.
    """

    def __init__(
        self,
        char_read_cb=None,
        char_write_cb=None,
        color_read_cb=None,
        color_write_cb=None,
    ):
        self.char_read_cb = char_read_cb
        self.color_read_cb = color_read_cb
        self.char_write_cb = char_write_cb
        self.color_write_cb = color_write_cb

        screen_size = hw_config.screen_size

        self.ram = bytearray(0x8000)  # 32KB RAM ($0000-$7FFF)
        self.rom = bytearray(0x1000)  # 4KB BIOS ROM ($F000-$FFFF)

        # Fallback local buffers in case no display callback is attached
        self._fallback_char_ram = bytearray(screen_size)
        self._fallback_color_ram = bytearray(screen_size)

        # Load BIOS binary into ROM if available
        try:
            with open(BIOS_FILE, "rb") as f:
                bios_data = f.read()
                copy_size = min(len(bios_data), len(self.rom))
                self.rom[:copy_size] = bios_data[:copy_size]
                print(
                    f"Loaded BIOS: {BIOS_FILE} ({len(bios_data)} 0x{len(bios_data):04X} bytes)"
                )
        except FileNotFoundError:
            print(f"WARNING: BIOS file not found: {BIOS_FILE}")
        except Exception as e:
            print(f"ERROR loading BIOS: {e}")

        # Dynamic memory map table using hardware configuration
        self.bus_map = [
            MemoryRange(
                name="ram",
                start=0x0000,
                len=hw_config.start_region_char_ram,
                read_cb=lambda offset: self.ram[offset],
                write_cb=self._write_ram,
            ),
            MemoryRange(
                name="chars",
                start=hw_config.start_region_char_ram,
                len=hw_config.screen_size,
                read_cb=self._read_char_mem,
                write_cb=self._write_char_mem,
            ),
            MemoryRange(
                name="colors",
                start=hw_config.start_region_color_ram,
                len=hw_config.screen_size,
                read_cb=self._read_color_mem,
                write_cb=self._write_color_mem,
            ),
            MemoryRange(
                name="bios",
                start=0xF000,
                end=0xFFFF,
                read_cb=lambda offset: self.rom[offset],
                # Explicitly no write_cb so writes to ROM are ignored
            ),
        ]

    # --- RAM Handlers ---
    def _write_ram(self, offset: int, value: int) -> None:
        self.ram[offset] = value & 0xFF

    # --- Character Memory Handlers ---
    def _read_char_mem(self, offset: int) -> int:
        # Emulated VRAM is authoritative. Never cross into the GUI merely to
        # service a 6502 memory read.
        return self._fallback_char_ram[offset]

    def _write_char_mem(self, offset: int, value: int) -> None:
        val = value & 0xFF
        if self._fallback_char_ram[offset] == val:
            return
        self._fallback_char_ram[offset] = val
        if self.char_write_cb:
            self.char_write_cb(offset, val)

    # --- Color Memory Handlers ---
    def _read_color_mem(self, offset: int) -> int:
        # As with character RAM, keep GUI access out of the CPU hot path.
        return self._fallback_color_ram[offset]

    def _write_color_mem(self, offset: int, value: int) -> None:
        val = value & 0xFF
        if self._fallback_color_ram[offset] == val:
            return
        self._fallback_color_ram[offset] = val
        if self.color_write_cb:
            self.color_write_cb(offset, val)

    def __getitem__(self, address: int) -> int:
        for m_range in self.bus_map:
            if m_range.contains(address):
                offset = address - m_range.start
                if m_range.read_cb:
                    return m_range.read_cb(offset)
                if m_range.default_read_val is not None:
                    return m_range.default_read_val
                break

        # Unmapped space returns NOP instruction ($EA)
        return 0xEA

    def __setitem__(self, address: int, value: int) -> None:
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
        char_read_cb=None,
        char_write_cb=None,
        color_read_cb=None,
        color_write_cb=None,
    ):
        reset_vector_address = 0xFFFC

        # Create system bus wired to full read/write callbacks
        self.bus = SystemBus(
            char_read_cb=char_read_cb,
            char_write_cb=char_write_cb,
            color_read_cb=color_read_cb,
            color_write_cb=color_write_cb,
        )

        # Create CPU starting at the reset vector
        reset_vector = self.bus[reset_vector_address] + (
            self.bus[reset_vector_address + 1] * 256
        )
        self.cpu = MPU(memory=self.bus, pc=reset_vector)

    def step(self) -> float:
        """Execute one instruction and return the cycles it consumed."""
        cycles_before = getattr(self.cpu, "processorCycles", None)
        self.cpu.step()
        cycles_after = getattr(self.cpu, "processorCycles", None)

        if cycles_before is not None and cycles_after is not None:
            elapsed_cycles = cycles_after - cycles_before
            if elapsed_cycles > 0:
                return float(elapsed_cycles)

        # Compatibility fallback for a py65 variant without processorCycles.
        return FALLBACK_CYCLES_PER_INSTRUCTION

    @property
    def has_native_cycle_counter(self) -> bool:
        """Return whether this py65 MPU exposes its accumulated cycle count."""
        return hasattr(self.cpu, "processorCycles")


class FConsole:
    """Main emulator controller managing both output windows."""

    def __init__(self) -> None:
        self.running = True
        self.isDirty = True

        # Coalesce repeated writes to the same cell. The display is updated by
        # a separate frame timer rather than from inside CPU execution.
        self._pending_char_writes: dict[int, int] = {}
        self._pending_color_writes: dict[int, int] = {}

        # Create windows
        self._create_video_window()
        self._create_debug_window()

        # Send test message directly to the dout text window
        self.console_print("Hello World!")

        # Initialize 6502 module with bidirectional video memory callbacks
        self.cpu_module = Cpu6502Module(
            char_read_cb=self._on_char_memory_read,
            char_write_cb=self._on_char_memory_write,
            color_read_cb=self._on_color_memory_read,
            color_write_cb=self._on_color_memory_write,
        )

        # Pacing state: emulated time is derived from completed CPU cycles.
        self._emulated_cycles = 0.0
        self._clock_origin = time.perf_counter()

    def _create_video_window(self) -> None:
        """Create the primary video output window."""
        print("Opening video output window (vout)...")

        if VIDEO_BACKEND == "text":
            self.vout = text_vd.Video(
                rows=SCREEN_ROWS,
                columns=SCREEN_COLS,
                scale=SCREEN_SCALE,
                font_family=TEXT_FONT_FAMILY,
            )
            print(
                "Text renderer: "
                f"font={self.vout.font_family!r}, "
                f"cell={self.vout.cell_width}x{self.vout.cell_height}px"
            )
        else:
            self.vout = bitmap_vd.Video(  # pyrefly: ignore[bad-assignment]
                rows=SCREEN_ROWS,
                columns=SCREEN_COLS,
                scale=SCREEN_SCALE,
            )
        self.vout._root.title("fcon - vout")
        self.vout._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_debug_window(self) -> None:
        """Create the debug output text window."""
        print("Opening debug output window (dout)...")

        self.dout_root = tk.Toplevel(self.vout._root)
        self.dout_root.title("fcon - dout")
        self.dout_root.geometry("600x400")
        self.dout_root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.debug_text = tk.Text(
            self.dout_root,
            wrap=tk.WORD,
            bg="black",
            fg="#00FF00",  # Green terminal text
            insertbackground="#00FF00",
        )
        self.debug_text.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

    def console_print(self, text: str) -> None:
        """Explicitly write text directly into the debug window (dout)."""
        if hasattr(self, "debug_text") and self.debug_text:
            self.debug_text.insert(tk.END, str(text) + "\n")
            self.debug_text.see(tk.END)

    # --- Bidirectional Video Callbacks ---
    def _on_char_memory_read(self, offset: int) -> int:
        """Compatibility callback; CPU reads use the bus-owned VRAM buffer."""
        return self.cpu_module.bus._fallback_char_ram[offset]

    def _on_char_memory_write(self, offset: int, value: int) -> None:
        """Queue a character-cell update for the next video frame."""
        self._pending_char_writes[offset] = value
        self.isDirty = True

    def _on_color_memory_read(self, offset: int) -> int:
        """Compatibility callback; CPU reads use the bus-owned VRAM buffer."""
        return self.cpu_module.bus._fallback_color_ram[offset]

    def _on_color_memory_write(self, offset: int, value: int) -> None:
        """Queue a color-cell update for the next video frame."""
        self._pending_color_writes[offset] = value
        self.isDirty = True

    def ord2(self, ch: str) -> int:
        return self.vout.get_screencode(ch)

    def _log_cpu_state_to_console(self) -> None:
        """Advance the 6502 CPU one instruction and log state to console window."""

        # vec = 0xFFFC
        vec = 0x00F0

        output_lines = [
            # f"PC: {pc:04X}",
            " A  X  Y SP NV-BDIZC Vector",
            "---------------------",
            f"{self.cpu_module.cpu.a:02X} "
            f"{self.cpu_module.cpu.x:02X} "
            f"{self.cpu_module.cpu.y:02X} "
            f"{self.cpu_module.cpu.sp:02X} "
            f"{(self.cpu_module.cpu.p >> 7) & 1}"
            f"{(self.cpu_module.cpu.p >> 6) & 1}"
            f"{(self.cpu_module.cpu.p >> 5) & 1}"
            f"-"
            f"{(self.cpu_module.cpu.p >> 3) & 1}"
            f"{(self.cpu_module.cpu.p >> 2) & 1}"
            f"{(self.cpu_module.cpu.p >> 1) & 1}"
            f"{self.cpu_module.cpu.p & 1}"
            f" {self.cpu_module.bus[vec + 1]:02X}"
            f"{self.cpu_module.bus[vec]:02X}",
            "",
        ]

        output = "\n".join(output_lines)
        self.console_print(output)
        print(output)

    def _update_cpu_step_debug(self) -> None:
        """Advance the 6502 CPU one instruction per tick and show state."""

        cols = SCREEN_COLS
        # rows = SCREEN_ROWS

        # Execute one NOP at a time from $0000
        self.cpu_module.step()

        # Show the current PC in hex so we can verify it advances
        pc = self.cpu_module.cpu.pc
        pc_str = f"{pc:04X}"

        for i, ch in enumerate(pc_str):
            row = 1
            col = 2 + i
            self.vout.set_screen(row * cols + col, self.ord2(ch))

        label = "PC"
        for i, ch in enumerate(label):
            row = 1
            col = i
            self.vout.set_screen(row * cols + col, self.ord2(ch))

        separator = "----------"
        for i, ch in enumerate(separator):
            row = 3
            col = i
            self.vout.set_screen(row * cols + col, self.ord2(ch))

        note = "ALL MEM=$EA ╝(NOP)"
        for i, ch in enumerate(note):
            row = 5
            col = i
            self.vout.set_screen(row * cols + col, self.ord2(ch))

        regs_label = "  A  X  Y  SP NV-BDIZC Vector"
        for i, ch in enumerate(regs_label):
            row = 7
            col = i
            self.vout.set_screen(row * cols + col, self.ord2(ch))

        reg_vals = (
            f"  "
            f"{self.cpu_module.cpu.a:02X} "
            f"{self.cpu_module.cpu.x:02X} "
            f"{self.cpu_module.cpu.y:02X} "
            f"{self.cpu_module.cpu.sp:02X} "
            f"{(self.cpu_module.cpu.p >> 7) & 1}"
            f"{(self.cpu_module.cpu.p >> 6) & 1}"
            f"{(self.cpu_module.cpu.p >> 5) & 1}"
            f"-"
            f"{(self.cpu_module.cpu.p >> 3) & 1}"
            f"{(self.cpu_module.cpu.p >> 2) & 1}"
            f"{(self.cpu_module.cpu.p >> 1) & 1}"
            f"{self.cpu_module.cpu.p & 1}"
            f" {self.cpu_module.bus[0xFFFD]:02X}"
            f"{self.cpu_module.bus[0xFFFC]:02X}"
        )
        for i, ch in enumerate(reg_vals):
            row = 8
            col = i
            self.vout.set_screen(row * cols + col, self.ord2(ch))

        # Refresh display
        self.vout.refresh_screen()

        # Schedule next frame (~15 FPS)
        if self.running:
            # self.vout._root.after(66, self._update_cpu_step)
            self.vout._root.after(0, self._update_cpu_step)

    def _update_video_frame(self) -> None:
        """Flush coalesced VRAM writes and redraw at a bounded frame rate."""
        if not self.running:
            return

        if self.isDirty:
            # A cell written ten times between frames is transferred once, with
            # only its final value.
            for offset, value in self._pending_char_writes.items():
                self.vout.set_screen(offset, value)
            for offset, value in self._pending_color_writes.items():
                self.vout.set_color(offset, value)

            self._pending_char_writes.clear()
            self._pending_color_writes.clear()
            self.vout.refresh_screen()
            self.isDirty = False

        self.vout._root.after(REFRESH_INTERVAL_MS, self._update_video_frame)

    def _update_cpu_step(self) -> None:
        """Execute one batch, then schedule the next batch at CPU-clock speed."""
        batch_cycles = 0.0

        for _ in range(INSTRUCTIONS_PER_BATCH):
            batch_cycles += self.cpu_module.step()

            n = self.cpu_module.bus[self.cpu_module.cpu.pc]
            # Break instruction
            if n == 0x00:
                self._log_cpu_state_to_console()

            if VID_DEBUG:
                self._update_cpu_step_debug()

        self._emulated_cycles += batch_cycles

        if not self.running:
            return

        now = time.perf_counter()
        target_time = self._clock_origin + (self._emulated_cycles / CPU_CLOCK_HZ)
        lag_seconds = now - target_time

        # A debugger stop, window drag, or overloaded host can leave the emulator
        # far behind. Do not burn a core indefinitely trying to replay old time.
        if lag_seconds > MAX_CATCH_UP_SECONDS:
            self._clock_origin = now - (self._emulated_cycles / CPU_CLOCK_HZ)
            target_time = now

        ahead_seconds = max(0.0, target_time - now)
        clock_delay_ms = math.ceil((ahead_seconds * 1000.0) - 1e-9)
        delay_ms = max(HOST_YIELD_MS, clock_delay_ms)
        self.vout._root.after(delay_ms, self._update_cpu_step)

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
        print("=" * 60)
        print("FCONSOLE EMULATOR")
        print("=" * 60)
        print(f"Video: {hw_config.screen_rows} rows x {hw_config.screen_cols} columns")
        print("Mode : py65 6502 (memory mapped bus table active)")
        print(f"Video: {VIDEO_BACKEND} backend")
        if VIDEO_BACKEND == "text":
            print("Copy : drag to select, Ctrl+C to copy; Ctrl+A selects all")
        cycle_mode = (
            "py65 processorCycles"
            if self.cpu_module.has_native_cycle_counter
            else f"fallback ({FALLBACK_CYCLES_PER_INSTRUCTION:g} cycles/instruction)"
        )
        print(f"Clock: {CPU_CLOCK_HZ:g} Hz; timing source: {cycle_mode}")
        print("\nClose either window to exit.\n")

        self._update_cpu_step()
        self._update_video_frame()

        # Tk's blocking event loop sleeps efficiently until an event or an
        # after() callback is ready. The previous update() polling loop spun at
        # full speed even while the emulated CPU was supposed to be paused.
        try:
            self.vout._root.mainloop()
        except tk.TclError:
            pass
        finally:
            if self.running:
                self._on_close()


def main():
    """Entry point for fconsole emulator."""
    print(
        "Config: "
        f"clock_hz={CPU_CLOCK_HZ:g} ({hw_config.clock_speed}), "
        f"instructions_per_batch={INSTRUCTIONS_PER_BATCH}, "
        f"fallback_cycles_per_instruction={FALLBACK_CYCLES_PER_INSTRUCTION:g}, "
        f"max_catch_up_ms={MAX_CATCH_UP_SECONDS * 1000:g}, "
        f"host_yield_ms={HOST_YIELD_MS}, "
        f"screen_scale={SCREEN_SCALE}, "
        f"refresh_hz={REFRESH_HZ:g}, "
        f"screen_size={hw_config.screen_cols}x{hw_config.screen_rows}, "
        f"video_backend={VIDEO_BACKEND}, "
        f"text_font_family={TEXT_FONT_FAMILY!r}"
    )
    console = FConsole()
    console.run()
    sys.exit(0)


if __name__ == "__main__":
    main()
