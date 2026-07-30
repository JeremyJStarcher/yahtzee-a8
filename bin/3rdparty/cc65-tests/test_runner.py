#!/usr/bin/env python3
"""test_runner.py — Black-box tests for the run_wasi.py launcher.

These tests exercise the launcher's error handling, argument forwarding,
and exit-code propagation.  They do not require the .wasm modules to
produce specific output beyond version/help strings.

Usage:
    python3 tests/test_runner.py
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUN_WASI = [sys.executable, str(REPO_ROOT / "run_wasi.py")]


def _run(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*RUN_WASI, *args],
        cwd=cwd or str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Tests that do NOT need .wasm modules
# ---------------------------------------------------------------------------

def test_no_args() -> None:
    """No arguments prints usage and exits non-zero."""
    proc = _run([])
    assert proc.returncode != 0, f"expected non-zero exit, got {proc.returncode}"
    assert "Usage:" in proc.stderr or "usage" in proc.stderr.lower()


def test_unknown_tool() -> None:
    """Unknown tool name produces a clear error."""
    proc = _run(["nonexistent_tool_xyz"])
    assert proc.returncode != 0
    assert "Unknown tool" in proc.stderr or "unknown" in proc.stderr.lower()


# ---------------------------------------------------------------------------
# Tests that REQUIRE .wasm modules
# ---------------------------------------------------------------------------

def test_ca65_version() -> None:
    """ca65 --version prints the version string and exits 0."""
    proc = _run(["ca65", "--version"])
    assert proc.returncode == 0, f"exit {proc.returncode}: {proc.stderr}"
    output = proc.stdout + proc.stderr
    assert "V2.19" in output, f"version not found in: {output!r}"


def test_ld65_version() -> None:
    """ld65 --version prints the version string and exits 0."""
    proc = _run(["ld65", "--version"])
    assert proc.returncode == 0, f"exit {proc.returncode}: {proc.stderr}"
    output = proc.stdout + proc.stderr
    assert "V2.19" in output


def test_da65_version() -> None:
    """da65 --version prints the version string and exits 0."""
    proc = _run(["da65", "--version"])
    assert proc.returncode == 0, f"exit {proc.returncode}: {proc.stderr}"
    output = proc.stdout + proc.stderr
    assert "V2.19" in output


def test_ca65_help() -> None:
    """ca65 --help prints usage and exits successfully."""
    proc = _run(["ca65", "--help"])
    output = proc.stdout + proc.stderr
    assert "Usage:" in output or "usage" in output.lower()


def test_ca65_nonexistent_input() -> None:
    """ca65 with a nonexistent input file fails with non-zero exit."""
    proc = _run(["ca65", "nonexistent_file_xyz.asm"])
    assert proc.returncode != 0


def test_relative_paths() -> None:
    """Invocation from a subdirectory with relative paths works."""
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        # Write a minimal 6502 source using a relative path
        asm_rel = "test.asm"
        obj_rel = "test.o"
        asm_abs = os.path.join(tmp, asm_rel)
        with open(asm_abs, "w") as f:
            f.write('  .code\n  nop\n')
        proc = _run(["ca65", "-o", obj_rel, asm_rel], cwd=tmp)
        assert proc.returncode == 0, f"exit {proc.returncode}: stderr={proc.stderr!r}"
        assert Path(tmp, obj_rel).is_file()


def test_spaces_in_paths() -> None:
    """Invocation from a directory containing spaces works with relative paths."""
    import tempfile, os
    with tempfile.TemporaryDirectory() as base:
        spaced = os.path.join(base, "with spaces")
        os.makedirs(spaced, exist_ok=True)
        asm_rel = "test.asm"
        obj_rel = "test.o"
        asm_abs = os.path.join(spaced, asm_rel)
        with open(asm_abs, "w") as f:
            f.write('  .code\n  nop\n')
        proc = _run(["ca65", "-o", obj_rel, asm_rel], cwd=spaced)
        assert proc.returncode == 0, f"exit {proc.returncode}: stderr={proc.stderr!r}"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    tests = [
        # no-module tests
        ("no_args", test_no_args),
        ("unknown_tool", test_unknown_tool),
        # module-required tests
        ("ca65_version", test_ca65_version),
        ("ld65_version", test_ld65_version),
        ("da65_version", test_da65_version),
        ("ca65_help", test_ca65_help),
        ("ca65_nonexistent_input", test_ca65_nonexistent_input),
        ("relative_paths", test_relative_paths),
        ("spaces_in_paths", test_spaces_in_paths),
    ]

    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as exc:
            print(f"  FAIL  {name}: {exc}")
            failed += 1
        except Exception as exc:
            print(f"  ERROR {name}: {exc}")
            failed += 1

    print(f"\n{failed} failure(s) out of {len(tests)} tests")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
