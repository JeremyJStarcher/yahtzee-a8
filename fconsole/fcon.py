#!/usr/bin/env python3
"""
Fconsole - Official Emulator Start Script

Opens video output (vout) and debug output (dout) windows,
runs a simple 6502 emulator demo via py65 on the video display.
"""

import sys
from dataclasses import dataclass
import tkinter as tk

from pylib import video_display as vd

try:
    from py65.devices.mpu6502 import MPU
except ImportError as e:
    print(f"ERROR: Missing dependency: {e}")
    print("Please install py65: pip install py65")
    sys.exit(1)



@dataclass
class MemoryRange:
    start: int
    end: int

rom1_range = MemoryRange(start=0xF000, end=0xFFFF)


class SystemBus:
    """Custom system bus using Python's dunder methods for memory access.

    Memory layout:
    - $0000-$7FFF: RAM (32KB)
    - $8000-$BFFF: Unmapped (returns $EA on read, no-op on write)
    - $C000-$FFFF: ROM (16KB)
    """

    def __init__(self):
        import os
        BIOS_FILE = "bios/bios.bin"
        self.ram = bytearray(0x8000)  # 32KB RAM ($0000-$7FFF)
        self.rom = bytearray(rom1_range.end - rom1_range.start + 1)  # +1 for inclusive end address

        # Load BIOS binary into ROM if available
        try:
            with open(BIOS_FILE, 'rb') as f:
                bios_data = f.read()
                copy_size = min(len(bios_data), len(self.rom))
                self.rom[:copy_size] = bios_data[:copy_size]
                print(f"Loaded BIOS: {BIOS_FILE} ({len(bios_data)} 0x{len(bios_data):04X} bytes)")
        except FileNotFoundError:
            print(f"WARNING: BIOS file not found: {BIOS_FILE}")
        except Exception as e:
            print(f"ERROR loading BIOS: {e}")

    def __getitem__(self, address):
        if address < 0x8000:
            return self.ram[address]
        elif rom1_range.start <= address <= rom1_range.end :
            return self.rom[address -  rom1_range.start]
        else:
            # Unmapped space returns NOP instruction ($EA)
            return 0xEA

    def __setitem__(self, address, value):
        if address < 0x8000:
            self.ram[address] = value
        elif 0xC000 <= address <= 0xFFFF:
            pass  # Ignore writes to ROM


class Cpu6502Module:
    """Simple wrapper for the py65 6502 emulator."""


    def __init__(self):
        RESET_VECTOR_ADDRESS = 0xFFFC

        # Create system bus with RAM and ROM using dunder methods
        self.bus = SystemBus()

        # Create CPU starting at the reset vector
        RESET_VECTOR = self.bus[RESET_VECTOR_ADDRESS] + (self.bus[RESET_VECTOR_ADDRESS+1] * 256)
        self.cpu = MPU(memory=self.bus, pc=RESET_VECTOR)

    def step(self) -> None:
        """Execute one instruction."""
        self.cpu.step()


class FConsole:
    """Main emulator controller managing both output windows."""

    def __init__(self) -> None:
        # Track running state
        self.running = True

        # Create windows
        self._create_video_window()
        self._create_debug_window()

        # Initialize 6502 module (RAM and ROM with $EA for unmapped space)
        self.cpu_module = Cpu6502Module()

    def _create_video_window(self) -> None:
        """Create the primary video output window."""
        print("Opening video output window (vout)...")

        # 24 rows x 40 columns, scale=3 for visibility
        self.vout = vd.Video(rows=24, columns=40, scale=3)

        # Override the default title to match requirement
        self.vout._root.title("fcon - vout")

        # Set up close handler
        self.vout._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_debug_window(self) -> None:
        """Create the debug output text window."""
        print("Opening debug output window (dout)...")

        self.dout_root = tk.Tk()
        self.dout_root.title("fcon - dout")
        self.dout_root.geometry("600x400")

        # Add a scrollable text widget for debug output
        self.debug_text = tk.Text(
            self.dout_root,
            wrap=tk.WORD,
            bg="black",
            fg="#00FF00",  # Green terminal-style text
            insertbackground="#00FF00",
        )
        self.debug_text.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

        # Redirect stdout/stderr to our debug window
        # self._original_stdout = sys.stdout
        # self._original_stderr = sys.stderr
        # sys.stdout = self._DebugWriter(self.debug_text)
        # sys.stderr = self._DebugWriter(self.debug_text)

    class _DebugWriter:
        """Helper class to redirect output to a Tkinter Text widget."""

        def __init__(self, text_widget) -> None:
            self.text_widget = text_widget
            self.buffer = ""
            self.alive = True

        def write(self, message) -> None:
            if not self.alive:
                return
            self.buffer += message
            # Schedule update on the main thread
            try:
                self.text_widget.after_idle(self._flush)
            except tk.TclError:
                self.alive = False

        def _flush(self) -> None:
            if not self.alive or not self.buffer:
                return
            try:
                self.text_widget.insert(tk.END, self.buffer)
                self.text_widget.see(tk.END)
                self.buffer = ""
            except (tk.TclError, AttributeError):
                self.alive = False

        def flush(self) -> None:
            pass

        def close(self) -> None:
            """Mark writer as closed to prevent further writes."""
            self.alive = False

    def ord2(self, ch: str) -> int:
        return self.vout.get_screencode(ch)

    def _update_cpu_step(self) -> None:
        """Advance the 6502 CPU one instruction per tick and show state."""
        cols = 40
        rows = 24

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

    def _on_close(self) -> None:
        """Handle vout window close."""
        self.running = False

        try:
            # Close debug writers first to stop scheduled callbacks
            if hasattr(sys.stdout, "close"):
                sys.stdout.close()
            if hasattr(sys.stderr, "close"):
                sys.stderr.close()

            # Restore original stdout/stderr
            sys.stdout = self._original_stdout
            sys.stderr = self._original_stderr

            # Close windows
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
        print("Mode : py65 6502 (memory filled with $EA NOPs)")
        print("\nClose the 'vout' window to exit.\n")

        # Start CPU stepping animation
        self._update_cpu_step()

        # Run both windows in their respective event loops
        self._run_event_loops()

    def _run_event_loops(self) -> None:
        """Run both Tkinter event loops cooperatively."""
        while self.running:
            try:
                # Update vout (this also processes its events via update_idletasks)
                if hasattr(self.vout, "_root") and self.vout._root is not None:
                    self.vout._root.update()

                # Update dout
                if hasattr(self, "dout_root") and self.dout_root is not None:
                    self.dout_root.update()

            except tk.TclError:
                # One of the windows was closed
                break

        # Cleanup
        self._on_close()


def main():
    """Entry point for fconsole emulator."""
    console = FConsole()
    console.run()
    sys.exit(0)


if __name__ == "__main__":
    main()
