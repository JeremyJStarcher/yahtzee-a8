#!/usr/bin/env python3
"""
Fconsole - Official Emulator Start Script

Opens video output (vout) and debug output (dout) windows,
runs a simple 6502 emulator demo via py65 on the video display.
"""

import sys
import argparse
from typing import Callable, Optional


def parse_args():
    """Parse command-line arguments with defaults matching current behavior."""
    parser = argparse.ArgumentParser(
        description="Fconsole - Official Emulator Start Script"
    )
    parser.add_argument(
        "--cycles-per-frame",
        type=int,
        default=8000,
        help="Number of CPU cycles per frame (default: 8000)",
    )
    parser.add_argument(
        "--screen-scale",
        type=int,
        default=2,
        help="Screen scaling factor (default: 2)",
    )
    return parser.parse_args()


args = parse_args()

import tkinter as tk
from dataclasses import dataclass

from pylib import video_display as vd

try:
    from py65.devices.mpu6502 import MPU
except ImportError as e:
    print(f"ERROR: Missing dependency: {e}")
    print("Please install py65: pip install py65")
    sys.exit(1)


CYCLES_PER_FRAME = args.cycles_per_frame
BIOS_FILE = "bios/bios.bin"
SCREEN_COLS = 40
SCREEN_ROWS = 24
SCREEN_SCALE = args.screen_scale


@dataclass
class MemoryRange:
    name: str
    start: int
    end: int = -1
    len: int = -1
    read_cb: Optional[Callable[[int], int]] = None
    write_cb: Optional[Callable[[int, int], None]] = None
    default_read_val: Optional[int] = None

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
        self.char_write_cb = char_write_cb
        self.color_read_cb = color_read_cb
        self.color_write_cb = color_write_cb

        screen_size = SCREEN_COLS * SCREEN_ROWS

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

        # Dynamic memory map table
        self.bus_map = [
            MemoryRange(
                name="ram",
                start=0x0000,
                len=0x8000,
                read_cb=lambda offset: self.ram[offset],
                write_cb=self._write_ram,
            ),
            MemoryRange(
                name="colors",
                start=0xC000,
                len=screen_size,
                read_cb=self._read_color_mem,
                write_cb=self._write_color_mem,
            ),
            MemoryRange(
                name="chars",
                start=0xE000,
                len=screen_size,
                read_cb=self._read_char_mem,
                write_cb=self._write_char_mem,
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
        if self.char_read_cb:
            return self.char_read_cb(offset) & 0xFF
        return self._fallback_char_ram[offset]

    def _write_char_mem(self, offset: int, value: int) -> None:
        val = value & 0xFF
        self._fallback_char_ram[offset] = val
        if self.char_write_cb:
            self.char_write_cb(offset, val)

    # --- Color Memory Handlers ---
    def _read_color_mem(self, offset: int) -> int:
        if self.color_read_cb:
            return self.color_read_cb(offset) & 0xFF
        return self._fallback_color_ram[offset]

    def _write_color_mem(self, offset: int, value: int) -> None:
        val = value & 0xFF
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

    def step(self) -> None:
        """Execute one instruction."""
        self.cpu.step()


class FConsole:
    """Main emulator controller managing both output windows."""

    def __init__(self) -> None:
        self.running = True
        self.isDirty = True

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

    def _create_video_window(self) -> None:
        """Create the primary video output window."""
        print("Opening video output window (vout)...")

        self.vout = vd.Video(rows=SCREEN_ROWS, columns=SCREEN_COLS, scale=SCREEN_SCALE)
        self.vout._root.title("fcon - vout")
        self.vout._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_debug_window(self) -> None:
        """Create the debug output text window."""
        print("Opening debug output window (dout)...")

        self.dout_root = tk.Tk()
        self.dout_root.title("fcon - dout")
        self.dout_root.geometry("600x400")

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
        """Read character byte directly from video display."""
        if hasattr(self.vout, "get_screen"):
            return self.vout.get_screen(offset)
        return 0

    def _on_char_memory_write(self, offset: int, value: int) -> None:
        """Handle writes to character memory - update video display."""
        self.vout.set_screen(offset, value)
        self.isDirty = True

    def _on_color_memory_read(self, offset: int) -> int:
        """Read color byte directly from video display."""
        if hasattr(self.vout, "get_color"):
            return self.vout.get_color(offset)
        return 0

    def _on_color_memory_write(self, offset: int, value: int) -> None:
        """Handle writes to color memory - update video display."""
        self.vout.set_color(offset, value)
        self.isDirty = True

    def ord2(self, ch: str) -> int:
        return self.vout.get_screencode(ch)

    def _update_cpu_step(self) -> None:
        """Advance the 6502 CPU instruction execution."""
        for _ in range(CYCLES_PER_FRAME):
            self.cpu_module.step()

        if self.isDirty:
            self.vout.refresh_screen()
            self.isDirty = False

        if self.running:
            self.vout._root.after(0, self._update_cpu_step)

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
        print(f"Video: {self.vout._rows} rows x {self.vout._columns} columns")
        print("Mode : py65 6502 (memory mapped bus table active)")
        print("\nClose the 'vout' window to exit.\n")

        self._update_cpu_step()
        self._run_event_loops()

    def _run_event_loops(self) -> None:
        """Run both Tkinter event loops cooperatively."""
        while self.running:
            try:
                if hasattr(self.vout, "_root") and self.vout._root is not None:
                    self.vout._root.update()

                if hasattr(self, "dout_root") and self.dout_root is not None:
                    self.dout_root.update()

            except tk.TclError:
                break

        self._on_close()


def main():
    """Entry point for fconsole emulator."""
    print(f"Config: cycles_per_frame={CYCLES_PER_FRAME}, screen_scale={SCREEN_SCALE}")
    console = FConsole()
    console.run()
    sys.exit(0)


if __name__ == "__main__":
    main()