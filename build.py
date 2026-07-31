#!/usr/bin/env python3
"""
build.py -- Cross-platform build script for yahtzee-a8.

Replaces all Makefiles with a single Python script.
Requires Python 3.12+.  No other dependencies beyond what's in the venv.

Usage:
    ./build.py bios              Build the 6502 BIOS
    ./build.py run               Build BIOS and run the emulator
    ./build.py run-text          Run with native Tk text renderer (preset)
    ./build.py run-bitmap        Run with bitmap renderer (preset)
    ./build.py clean             Remove all build artifacts
    ./build.py lint              Run ruff + pyrefly
    ./build.py format            Format Python sources (ruff)
    ./build.py format-asm        Format 6502 assembly sources (fmt6502)
    ./build.py typecheck         Type-check Python sources (pyrefly)

Run options (forwarded to fcon.py):
    ./build.py run --clock-hz 2000000 --video-backend text --screen-scale 2
    ./build.py run -- --text-font-family "DejaVu Sans Mono"

Pass '--' before extra args to avoid argparse consuming them:
    ./build.py run --clock-hz 2000000 -- --text-font-family "DejaVu Sans Mono"
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Absolute path to the repository root (where this script lives)."""
    return Path(__file__).resolve().parent


def _venv_dir() -> Path:
    """Hostname-keyed venv directory, matching the venv.mk scheme."""
    hostname = platform.node() or "unknown"
    return _repo_root() / "venv" / "hosts" / f"venv-{hostname}"


def _venv_python() -> Path:
    """Path to the venv Python interpreter."""
    return _venv_dir() / "bin" / "python"


def _run_wasi_script() -> Path:
    return _repo_root() / "bin" / "run_wasi.py"


# ---------------------------------------------------------------------------
# Venv management
# ---------------------------------------------------------------------------

def ensure_venv() -> Path:
    """Create the venv if it doesn't exist; install requirements.txt.

    Returns the path to the venv Python interpreter.
    """
    vdir = _venv_dir()
    vpy = _venv_python()

    if vdir.is_dir():
        return vpy

    print(f"Creating virtualenv at {vdir} ...")
    vdir.parent.mkdir(parents=True, exist_ok=True)

    r = subprocess.run(
        [sys.executable, "-m", "venv", str(vdir)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        _die(f"Failed to create venv:\n{r.stderr}", cleanup=vdir)

    # Upgrade packaging tools (best-effort)
    subprocess.run(
        [str(vpy), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        capture_output=True,
    )

    # Install requirements
    req = _repo_root() / "venv" / "requirements.txt"
    r = subprocess.run(
        [str(vpy), "-m", "pip", "install", "-r", str(req)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        _die(f"Failed to install requirements:\n{r.stderr}", cleanup=vdir)

    print(f"Virtualenv ready at {vdir}")
    return vpy


# ---------------------------------------------------------------------------
# WASI tool runner
# ---------------------------------------------------------------------------

def _wasi(venv_py: Path, tool: str, *args: str,
          cwd: Path | None = None) -> None:
    """Run a WASI tool via run_wasi.py.  Exits on failure."""
    cmd = [str(venv_py), str(_run_wasi_script()), tool, *args]
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        sys.exit(r.returncode)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _die(msg: str, cleanup: Path | None = None, code: int = 1) -> None:
    print(f"build.py: error: {msg}", file=sys.stderr)
    if cleanup is not None:
        shutil.rmtree(cleanup, ignore_errors=True)
    sys.exit(code)


def _rm_glob(directory: Path, *patterns: str) -> None:
    """Remove files matching glob patterns under *directory*."""
    root = _repo_root()
    for pat in patterns:
        for f in directory.glob(pat):
            if f.is_file():
                f.unlink()
                print(f"  rm {f.relative_to(root)}")


def _run(*args: str, cwd: Path | None = None) -> None:
    """Run a command; exit with its return code on failure."""
    r = subprocess.run([str(a) for a in args], cwd=cwd)
    if r.returncode != 0:
        sys.exit(r.returncode)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_bios(args: argparse.Namespace) -> None:
    """Assemble and link the 6502 BIOS."""
    vpy = ensure_venv()
    d = _repo_root() / "fconsole" / "bios"

    print("Assembling src/bios.asm ...")
    _wasi(vpy, "ca65", "--cpu", "6502", "--debug-info",
          "-o", "src/bios.o", "src/bios.asm", cwd=d)

    print("Assembling src/vectors.asm ...")
    _wasi(vpy, "ca65", "--cpu", "6502", "--debug-info",
          "-o", "src/vectors.o", "src/vectors.asm", cwd=d)

    print("Linking bios.bin ...")
    _wasi(vpy, "ld65", "-C", "bios.cfg", "-m", "bios.bin.map",
          "-o", "bios.bin", "src/bios.o", "src/vectors.o", cwd=d)

    print("Disassembling bios.bin -> bios.lst ...")
    _wasi(vpy, "da65", "--cpu", "6502", "--start-addr", "$F000",
          "--multi-pass", "-o", "bios.lst", "bios.bin", cwd=d)

    print("BIOS build complete.")


def cmd_run(args: argparse.Namespace) -> None:
    """Build BIOS and launch the emulator."""
    cmd_bios(args)

    vpy = ensure_venv()
    d = _repo_root() / "fconsole"

    fcon_args = [
        "--clock-hz", str(args.clock_hz),
        "--instructions-per-batch", str(args.instructions_per_batch),
        "--screen-scale", str(args.screen_scale),
        "--video-backend", args.video_backend,
        "--refresh-hz", str(args.refresh_hz),
    ]
    if args.extra:
        fcon_args.extend(args.extra)

    print(f"Running fcon.py with: {' '.join(fcon_args)}")
    r = subprocess.run([str(vpy), "fcon.py", *fcon_args], cwd=d)
    sys.exit(r.returncode)


def cmd_clean(args: argparse.Namespace) -> None:
    """Remove all build artifacts."""
    root = _repo_root()

    _rm_glob(root / "fconsole" / "bios",
             "bios.bin", "bios.bin.map", "bios.lst",
             "src/bios.o", "src/vectors.o", "src/*.lst")
    _rm_glob(root / "fconsole", "*.pyc")
    _rm_glob(root / "src", "hello.o", "hello.xex")
    print("Clean complete.")


def cmd_lint(args: argparse.Namespace) -> None:
    """Run ruff and pyrefly linters."""
    ensure_venv()
    vdir = _venv_dir()
    d = _repo_root() / "fconsole"
    _run(vdir / "bin" / "ruff", "check", ".", "--fix", cwd=d)
    _run(vdir / "bin" / "pyrefly", "check", ".", cwd=d)


def cmd_format(args: argparse.Namespace) -> None:
    """Format Python sources with ruff."""
    ensure_venv()
    _run(_venv_dir() / "bin" / "ruff", "format", ".",
         cwd=_repo_root() / "fconsole")


def cmd_format_asm(args: argparse.Namespace) -> None:
    """Format 6502 assembly sources with fmt6502."""
    vpy = ensure_venv()
    bios_d = _repo_root() / "fconsole" / "bios"
    fmt_script = _repo_root() / "dev-tools" / "fmt6502" / "fmt6502.py"

    sources = [
        "src/bios.asm", "src/vectors.asm",
        "src/branches.inc", "src/math.inc", "src/hw_limits.inc",
    ]
    _run(vpy, fmt_script,
         "--strict", "--indent-size", "4",
         "--comment-indent", "40", "--min-comment-gap", "2",
         "--in-place", *sources,
         cwd=bios_d)


def cmd_typecheck(args: argparse.Namespace) -> None:
    """Type-check Python sources with pyrefly."""
    ensure_venv()
    _run(_venv_dir() / "bin" / "pyrefly", "check", ".",
         cwd=_repo_root() / "fconsole")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _add_run_args(parser: argparse.ArgumentParser,
                  clock_hz: float = 1_000_000,
                  instructions_per_batch: int = 2_000,
                  screen_scale: int = 4,
                  video_backend: str = "bitmap",
                  refresh_hz: float = 60) -> None:
    """Add the standard run-option flags to a subparser."""
    parser.add_argument("--clock-hz", type=float, default=clock_hz,
                        help="Target emulated CPU clock in Hz (default: %(default)s)")
    parser.add_argument("--instructions-per-batch", type=int,
                        default=instructions_per_batch,
                        help="Max instructions per batch (default: %(default)s)")
    parser.add_argument("--screen-scale", type=int, default=screen_scale,
                        help="Screen scaling factor (default: %(default)s)")
    parser.add_argument("--refresh-hz", type=float, default=refresh_hz,
                        help="Max display refresh rate in Hz (default: %(default)s)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="yahtzee-a8 cross-platform build script",
    )
    sp = parser.add_subparsers(dest="command")
    sp.required = True

    # ---- bios ----
    sp.add_parser("bios", help="Build the 6502 BIOS").set_defaults(func=cmd_bios)

    # ---- run (configurable) ----
    p_run = sp.add_parser("run", help="Build BIOS and run the emulator")
    _add_run_args(p_run, clock_hz=1_000_000, instructions_per_batch=2_000,
                  screen_scale=4, refresh_hz=60)
    p_run.add_argument("--video-backend", choices=("bitmap", "text"),
                       default="bitmap",
                       help="Video renderer (default: %(default)s)")
    p_run.add_argument("extra", nargs="*", default=[],
                       help="Extra arguments forwarded to fcon.py")
    p_run.set_defaults(func=cmd_run)

    # ---- run-text (preset) ----
    p_rt = sp.add_parser("run-text",
                          help="Run with native Tk text renderer (preset)")
    _add_run_args(p_rt, clock_hz=1_000_000, instructions_per_batch=2_000,
                  screen_scale=4, refresh_hz=60)
    p_rt.add_argument("extra", nargs="*", default=[])
    p_rt.set_defaults(func=cmd_run, video_backend="text")

    # ---- run-bitmap (preset) ----
    p_rb = sp.add_parser("run-bitmap",
                          help="Run with bitmap renderer (preset)")
    _add_run_args(p_rb, clock_hz=1_000_000, instructions_per_batch=2_000,
                  screen_scale=4, refresh_hz=30)
    p_rb.add_argument("extra", nargs="*", default=[])
    p_rb.set_defaults(func=cmd_run, video_backend="bitmap")

    # ---- clean ----
    sp.add_parser("clean",
                  help="Remove all build artifacts").set_defaults(func=cmd_clean)

    # ---- lint ----
    sp.add_parser("lint",
                  help="Run ruff + pyrefly").set_defaults(func=cmd_lint)

    # ---- format ----
    sp.add_parser("format",
                  help="Format Python sources (ruff)").set_defaults(func=cmd_format)

    # ---- format-asm ----
    sp.add_parser("format-asm",
                  help="Format 6502 assembly sources (fmt6502)").set_defaults(func=cmd_format_asm)

    # ---- typecheck ----
    sp.add_parser("typecheck",
                  help="Type-check Python sources (pyrefly)").set_defaults(func=cmd_typecheck)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
