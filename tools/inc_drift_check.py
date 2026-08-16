#!/usr/bin/env python3
"""inc_drift_check.py -- fail if mirrored ca65 library copies have drifted.

The kernel tree (fconsole/bios/src/) and the user-land tree
(app/hosts/shared/) each carry a copy of branches.inc / math.inc /
hw_limits.inc because WASI ca65 can only read its own current directory
and the two trees are separate builds.  The copies must stay byte-identical;
the kernel side is the source of truth.

Run from anywhere (paths resolved relative to this file):

    python3 tools/inc_drift_check.py

Exit codes:
    0 all mirror pairs identical
    1 one or more pairs diverge, or an expected file is missing
    2 unexpected error

Intentionally NOT checked: bin/3rdparty/cc65-asm-tests/bios/src/*.inc --
that tree is an independent cc65 toolchain fixture snapshot kept in sync
with upstream, not part of the kernel/user-land mirror pair.
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL_DIR = ROOT / "fconsole" / "bios" / "src"
USERLAND_DIR = ROOT / "app" / "hosts" / "shared"
NAMES = ("branches.inc", "math.inc", "hw_limits.inc")


def diff_text(a: Path, b: Path, ka: bytes, kb: bytes) -> str:
    la = ka.decode("utf-8", errors="replace").splitlines(keepends=True)
    lb = kb.decode("utf-8", errors="replace").splitlines(keepends=True)
    return "".join(difflib.unified_diff(
        la, lb,
        fromfile=str(a.relative_to(ROOT)),
        tofile=str(b.relative_to(ROOT)),
        lineterm="",
    ))


def main() -> int:
    failures = 0
    for name in NAMES:
        k = KERNEL_DIR / name
        u = USERLAND_DIR / name
        if not k.is_file() or not u.is_file():
            print(f"DRIFT CHECK FAIL: {name} missing on one side "
                  f"(kernel={k.is_file()}, userland={u.is_file()})")
            failures += 1
            continue
        kb, ub = k.read_bytes(), u.read_bytes()
        if kb == ub:
            print(f"ok   {name} (identical)")
        else:
            failures += 1
            print(f"FAIL {name}: kernel and user-land copies differ.")
            sys.stdout.write(diff_text(k, u, kb, ub) + "\n")
            print("Edit the kernel copy, then sync it to the user-land tree "
                  "(see the MIRROR FILE banner at the top of each file).")

    if failures:
        print(f"\ninc_drift_check: {failures} pair(s) diverged.")
        return 1
    print("\ninc_drift_check: all mirror pairs identical.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - unexpected I/O etc.
        print(f"inc_drift_check error: {exc!r}")
        raise SystemExit(2)
