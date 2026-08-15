#!/usr/bin/env python3
"""Headless fconsole runner: executes the host program under the real BIOS
and reports the emulated console output instead of opening GUI windows."""

from __future__ import annotations

import os
import sys
from pathlib import Path

FCON = Path(__file__).resolve().parents[1] / ".." / "fconsole"
sys.path.insert(0, str(FCON))

import fcon as F  # noqa: E402

BIN = Path(sys.argv[1]) if len(sys.argv) > 1 else (Path(__file__).resolve().parents[1] / "hosts/fconsole.bin")
LST = Path(__file__).resolve().parents[1] / "hosts/fconsole.lst"


def _load_screen_to_ascii() -> list[str]:
    """Inverse of the BIOS p2s (print code -> screen code) translation table."""
    import re as _re

    lines = (FCON / "pylib/p2s_xlate.inc").read_text().splitlines()
    flat: list[int] = []
    for line in lines:
        flat.extend(int(v, 16) for v in _re.findall(r"\$([0-9A-Fa-f]{2})", line))
    assert len(flat) == 256, f"expected 256 entries, got {len(flat)}"
    s2p = ["" for _ in range(256)]
    for print_code, screen_code in enumerate(flat):
        if not s2p[screen_code]:
            s2p[screen_code] = chr(print_code)
    # Force newline semantics on CHAR_NL's ($0A) screen code.
    s2p[flat[0x0A]] = "\n"
    return s2p


S2P = _load_screen_to_ascii()


LBL = Path(__file__).resolve().parents[1] / "hosts/fconsole.lbl"


def label_addr(name: str) -> int | None:
    """Absolute RAM address of a ZEROPAGE label, via the ca65 .lbl file.

    The linker maps ZEROPAGE at $0000, so the listed offset is directly an
    absolute address.
    """
    import re

    with open(LBL) as f:
        for m in re.finditer(r"^al ([0-9A-Fa-f]+) (?:\.)?([A-Za-z_][^\s]*)$", f.read(), re.M):
            if m.group(2) == name:
                return int(m.group(1), 16)
    return None


fail_flag = label_addr("fail_flag")
math_fail_flag = label_addr("math_fail_flag")
print(f"fail_flag=${fail_flag:X}  math_fail_flag=${math_fail_flag:X}")

from py65.devices.mpu6502 import MPU  # noqa: E402

cfg = F.EmulatorConfig(
    screen_cols=40,
    screen_rows=24,
    screen_scale=1,
    video_backend="text",
    text_font_family=None,
    instructions_per_batch=8000,
    clock_hz=3_000_000,
    fallback_cycles_per_instruction=3.0,
    max_catch_up_seconds=0.1,
    host_yield_ms=1,
    refresh_interval_ms=1000,
    screen_size=960,
    start_region_char_ram=0xA000,
    start_region_color_ram=0xB000,
    bios_file=str(FCON / "bios/bios.bin"),
)

cpu_mod = F.Cpu6502Module(cfg, MPU)
cpu_mod.load_program(str(BIN))

STEP_LIMIT = int(os.environ.get("STEP_LIMIT", "4000000"))
FROZEN_REPEATS = 500

last_pc = None
repeat_count = 0
halted = False
frozen = False
failed_flags: list[str] = []


def flags_now() -> tuple[int | None, int | None]:
    bus = cpu_mod.bus.ram
    f1 = bus[fail_flag] if fail_flag is not None else None
    f2 = bus[math_fail_flag] if math_fail_flag is not None else None
    return f1, f2


def decode_screen() -> str:
    ram = cpu_mod.bus._fallback_char_ram
    out = []
    for row_start in range(0, len(ram), 40):
        cells = [S2P[b] or "?" for b in ram[row_start : row_start + 40]]
        out.append("".join(cells))
    return "\n".join(out)


for step in range(STEP_LIMIT):
    pc_before = getattr(cpu_mod.cpu, "pc", None)
    pc_before = (pc_before & 0xFFFF) if pc_before is not None else -1
    cpu_mod.step()

    # Progress trace: report which test names are currently visible.
    if step and step % 50_000 == 0:
        text_now = decode_screen()
        if "HALTED" in text_now:
            halted = True
            break
        visible = [l.rstrip() for l in text_now.split("\n") if l.strip()]
        print(f"[{step}] last lines: {visible[-3:]}", flush=True)

    # Freeze-loop detection (the test suites freeze on the first failure).
    pc_after = cpu_mod.cpu.pc & 0xFFFF
    if last_pc is not None and (pc_after == last_pc or abs(pc_after - last_pc) <= 3):
        repeat_count += 1
    else:
        repeat_count = 0
    last_pc = pc_after
    if repeat_count > 1500:
        f1, f2 = flags_now()
        if (f1 or f2) and step >= 50_000:
            frozen = True
            failed_flags = [n for n, v in (("branch(fail_flag)", f1), ("math(math_fail_flag)", f2)) if v]
            break
        elif not (f1 or f2) and step > int(STEP_LIMIT * 0.9):
            # Frozen but no fail flag set: something else is looping.
            frozen = True
            break

text = decode_screen()

print("=== emulated console ===")
for line in text.split("\n"):
    print(line.rstrip())

if "FAILED" in text:
    print("\nRESULT: FAILED — a test reported failure before freezing.")
    sys.exit(1)
if halted:
    print("\nRESULT: PASSED — all tests completed, HALTED reached.")
elif frozen:
    print(f"\nRESULT: FROZEN without FAIL flags -> {failed_flags or 'unknown loop'}")
    sys.exit(2)
else:
    print(f"\nRESULT: still running after {STEP_LIMIT} steps (no HALTED).")
    sys.exit(3)
