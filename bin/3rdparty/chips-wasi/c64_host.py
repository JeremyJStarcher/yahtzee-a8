#!/usr/bin/env python3
"""c64_host.py — Thin host wrapper for the C64 chips WASI module.

Usage:
    python3 c64_host.py                  # interactive pygame, scale 2
    python3 c64_host.py --headless --frames 300 --preview
    python3 c64_host.py --type 'PRINT"HI"^M' --preview
"""

import sys

import commodore_host


def main() -> int:
    defaults = {
        "wasm": "c64.wasm",
        "fbw": 392,
        "fbh": 272,
        "title": "C64",
        "scale": 2,
    }
    parser = commodore_host.build_parser(defaults)
    args = parser.parse_args()

    emu = commodore_host.Emulator(args.wasm, args.fbw, args.fbh)
    emu.init()

    if args.headless or args.frames or args.dump or args.preview or args.type:
        commodore_host.run_headless(emu, args)
        return 0

    try:
        import pygame  # noqa: F401
    except ImportError:
        print("pygame not available; running headless (120 frames).", file=sys.stderr)
        args.pre_frames = 0
        args.post_frames = 120
        commodore_host.run_headless(emu, args)
        return 0

    commodore_host.run_pygame(emu, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
