#!/usr/bin/env python3
"""test_cc65_pipeline.py — Integration test: assemble, link, and verify the BIOS.

This is the canonical acceptance test: run the full ca65 → ld65 pipeline
through run_wasi.py and confirm the output matches the golden BIOS image.

Usage:
    python3 tests/test_cc65_pipeline.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RUN_WASI = [sys.executable, str(REPO_ROOT / "bin/run_wasi.py")]
GOLDEN = REPO_ROOT / "bin/3rdparty/cc65-asm-tests/verify" / "bios-orig.bin"
COMPARE = [sys.executable, str(REPO_ROOT / "bin/3rdparty/cc65-tests" / "compare_binary.py")]


def test_bios_pipeline(tmp_path: Path) -> None:
    """Assemble and link the BIOS from a temp dir, then compare with golden."""
    bios_src = REPO_ROOT / "bin/3rdparty/cc65-asm-tests/bios" / "src"
    bios_cfg = REPO_ROOT / "bin/3rdparty/cc65-asm-tests/bios" / "bios.cfg"

    # Copy source tree and config into the temp dir so we can use
    # relative paths (the WASI guest only sees CWD as ".").
    tmp_src = tmp_path / "src"
    shutil.copytree(bios_src, tmp_src)
    shutil.copy2(bios_cfg, tmp_path / "bios.cfg")

    bios_o = "src/bios.o"
    vectors_o = "src/vectors.o"
    bios_bin = "bios.bin"

    # Assemble
    for obj, src in [(bios_o, "src/bios.asm"), (vectors_o, "src/vectors.asm")]:
        proc = subprocess.run(
            [*RUN_WASI, "ca65", "--cpu", "6502", "--debug-info",
             "-o", obj, src],
            cwd=str(tmp_path),
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, (
            f"ca65 {src} failed (exit {proc.returncode}):\n{proc.stderr}"
        )
        assert (tmp_path / obj).is_file(), f"Object file not created: {obj}"

    # Link
    proc = subprocess.run(
        [*RUN_WASI, "ld65", "-C", "bios.cfg",
         "-o", bios_bin, bios_o, vectors_o],
        cwd=str(tmp_path),
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"ld65 failed (exit {proc.returncode}):\n{proc.stderr}"
    )
    assert (tmp_path / bios_bin).is_file(), f"BIOS binary not created: {bios_bin}"

    # Verify
    proc = subprocess.run(
        [*COMPARE, str(tmp_path / bios_bin), str(GOLDEN)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"BIOS comparison failed:\n{proc.stdout}\n{proc.stderr}"
    )


def test_bios_makefile() -> None:
    """Run 'make' in bios/ and verify the output matches the golden image."""
    bios_dir = REPO_ROOT / "bin/3rdparty/cc65-asm-tests/bios"

    # Clean
    subprocess.run(["make", "clean"], cwd=str(bios_dir),
                   capture_output=True, check=True)

    # Build
    proc = subprocess.run(["make"], cwd=str(bios_dir),
                          capture_output=True, text=True)
    assert proc.returncode == 0, (
        f"BIOS make failed (exit {proc.returncode}):\n{proc.stderr}"
    )

    bios_bin = bios_dir / "bios.bin"
    assert bios_bin.is_file(), f"bios.bin not created"

    # Verify
    proc = subprocess.run(
        [*COMPARE, str(bios_bin), str(GOLDEN)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"BIOS make comparison failed:\n{proc.stdout}"
    )


def main() -> int:
    import tempfile

    failed = 0

    # Test 1: pipeline from scratch in a temp directory
    print("--- Pipeline test (temp directory) ---")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            test_bios_pipeline(Path(tmp))
        print("  PASS  bios_pipeline")
    except AssertionError as exc:
        print(f"  FAIL  bios_pipeline: {exc}")
        failed += 1
    except Exception as exc:
        print(f"  ERROR bios_pipeline: {exc}")
        failed += 1

    # Test 2: pipeline via the BIOS Makefile
    print("--- Pipeline test (bios/Makefile) ---")
    try:
        test_bios_makefile()
        print("  PASS  bios_makefile")
    except AssertionError as exc:
        print(f"  FAIL  bios_makefile: {exc}")
        failed += 1
    except Exception as exc:
        print(f"  ERROR bios_makefile: {exc}")
        failed += 1

    print(f"\n{failed} failure(s) out of 2 tests")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
