#!/usr/bin/env python3
"""
Fconsole - Official Emulator Start Script

Opens video output (vout) and debug output (dout) windows,
runs a bouncing asterisk demo on the video display.
"""

import sys
import tkinter as tk

from pylib import video_display as vd


class FConsole:
    """Main emulator controller managing both output windows."""

    def __init__(self) -> None:
        # Track running state
        self.running = True

        # Bouncing star state: position and velocity
        self.star_x = 0
        self.star_y = 0
        self.vel_x = 1
        self.vel_y = 1

        # Create windows
        self._create_video_window()
        self._create_debug_window()

    def _create_video_window(self) -> None:
        """Create the primary video output window."""
        print("Opening video output window (vout)...")

        # 24 rows x 40 columns, scale=2 for visibility
        self.vout = vd.Video(rows=24, columns=40, scale=3)

        # Override the default title to match requirement
        self.vout._root.title("fcon - vout")

        # Initialize star at center of screen
        cols = 40
        rows = 24
        self.star_x = cols // 2
        self.star_y = rows // 2

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
            insertbackground="#00FF00"
        )
        self.debug_text.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

        # Redirect stdout/stderr to our debug window
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = self._DebugWriter(self.debug_text)
        sys.stderr = self._DebugWriter(self.debug_text)

        # Don't block on this window's mainloop - we'll run it separately

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

    def _update_bounce(self) -> None:
        """Update star position with bouncing logic."""
        cols = 40
        rows = 24

        # Erase old position (set to space)
        self.vout.set_screen(self.star_y * cols + self.star_x, ord(' '))

        # Move star
        self.star_x += self.vel_x
        self.star_y += self.vel_y

        # Bounce off horizontal walls
        if self.star_x <= 0 or self.star_x >= cols - 1:
            self.vel_x *= -1
            self.star_x = max(0, min(cols - 1, self.star_x))

        # Bounce off vertical walls
        if self.star_y <= 0 or self.star_y >= rows - 1:
            self.vel_y *= -1
            self.star_y = max(0, min(rows - 1, self.star_y))

        # Draw new position
        self.vout.set_screen(self.star_y * cols + self.star_x, ord('*'))

        # Refresh display
        self.vout.refresh_screen()

        # Schedule next frame (~15 FPS for visible smooth animation)
        if self.running:
            self.vout._root.after(66, self._update_bounce)

    def _on_close(self) -> None:
        """Handle vout window close."""
        self.running = False

        try:
            # Close debug writers first to stop scheduled callbacks
            if hasattr(sys.stdout, 'close'):
                sys.stdout.close()
            if hasattr(sys.stderr, 'close'):
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
        print("Animation: Bouncing asterisk demo")
        print("\nClose the 'vout' window to exit.\n")

        # Start animation
        self._update_bounce()

        # Run both windows in their respective event loops
        # We need to handle both Tkinter instances
        self._run_event_loops()

    def _run_event_loops(self) -> None:
        """Run both Tkinter event loops cooperatively."""
        while self.running:
            try:
                # Update vout (this also processes its events via update_idletasks)
                if hasattr(self.vout, '_root') and self.vout._root is not None:
                    self.vout._root.update()

                # Update dout
                if hasattr(self, 'dout_root') and self.dout_root is not None:
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
