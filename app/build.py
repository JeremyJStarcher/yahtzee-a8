#!/usr/bin/env python3.12
"""Cross-platform project build driver.  Python 3.12+, stdlib only."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".." / "venv" / "venv-ours"
REQS = ROOT / ".."/ "venv" / "requirements.txt"
RUN_WASI = ROOT / ".." / "bin" / "run_wasi.py"
# Kernel tree holds the emulator itself.  User-land images are passed to it
# via --load; the BIOS is a raw image configured on the emulator side.
FCON_DIR = ROOT.parent / "fconsole"


# ---------------------------------------------------------------------------
# Process / environment helpers
# ---------------------------------------------------------------------------

def venv_tool(name: str) -> Path:
    bindir = VENV / ("Scripts" if sys.platform == "win32" else "bin")
    return bindir / (name + (".exe" if sys.platform == "win32" else ""))


def run(*cmd: str | Path, cwd: Path | None = None, check: bool = True,
        capture: bool = False) -> subprocess.CompletedProcess[str]:
    r = subprocess.run(
        [str(x) for x in cmd], cwd=cwd, text=True, capture_output=capture
    )
    if check and r.returncode:
        if capture:
            sys.stdout.write(r.stdout)
            sys.stderr.write(r.stderr)
        raise SystemExit(r.returncode)
    return r


def ensure_venv() -> Path:
    py = venv_tool("python")
    if py.is_file():
        return py

    if VENV.exists():
        shutil.rmtree(VENV, ignore_errors=True)

    print(f"Creating virtualenv at {VENV} ...")
    VENV.parent.mkdir(parents=True, exist_ok=True)

    r = run(sys.executable, "-m", "venv", VENV, capture=True, check=False)
    if r.returncode:
        shutil.rmtree(VENV, ignore_errors=True)
        raise SystemExit(f"build.py: failed to create venv:\n{r.stderr}")

    run(py, "-m", "pip", "install", "--upgrade",
        "pip", "setuptools", "wheel", capture=True, check=False)

    r = run(py, "-m", "pip", "install", "-r", REQS,
            capture=True, check=False)
    if r.returncode:
        shutil.rmtree(VENV, ignore_errors=True)
        raise SystemExit(f"build.py: failed to install requirements:\n{r.stderr}")

    return py


def wasi(py: Path, tool: str, *args: str | Path, cwd: Path) -> None:
    run(py, RUN_WASI, tool, *args, cwd=cwd)


def stale(outputs: list[Path], inputs: list[Path], force: bool = False) -> bool:
    """Conservative make-style timestamp check."""
    if force or any(not p.is_file() for p in outputs):
        return True
    if any(not p.is_file() for p in inputs):
        missing = next(p for p in inputs if not p.is_file())
        raise SystemExit(f"build.py: missing input: {missing.relative_to(ROOT)}")
    return max(p.stat().st_mtime_ns for p in inputs) > min(
        p.stat().st_mtime_ns for p in outputs
    )


# ---------------------------------------------------------------------------
# Assembly targets
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AsmTarget:
    directory: str
    sources: tuple[str, ...]
    config: str
    output: str
    start: str
    description: str
    includes: tuple[str, ...] = ()
    cpu: str = "6502"

    @property
    def stem(self) -> str:
        return Path(self.output).stem

    @property
    def objects(self) -> tuple[str, ...]:
        return tuple(str(Path(x).with_suffix(".o")) for x in self.sources)

    @property
    def listings(self) -> tuple[str, ...]:
        return tuple(str(Path(x).with_suffix(".lst")) for x in self.sources)

    @property
    def map(self) -> str:
        return f"{self.stem}.map"

    @property
    def dbg(self) -> str:
        return f"{self.stem}.dbg"

    @property
    def labels(self) -> str:
        return f"{self.stem}.lbl"

    @property
    def disasm(self) -> str:
        return f"{self.stem}.disasm.asm"


TARGETS = {
    "fconsole": AsmTarget(
        directory="hosts",
        sources=("fconsole.asm",),
        config="fcon.cfg",
        output="fconsole.bin",
        # Image layout per fcon.cfg: VECTORS at %S - 4 ($02FC) is written to
        # file offset 0, then RAM/CODE from __RAM_START__ ($0300). da65 must
        # be told the address of file byte 0 or the first page of code and
        # the vectors are missing from the round-trip disassembly.
        start="$02FC",
        description="Assemble, link, disassemble the user-land host image",
        # Everything .include'd by fconsole.asm (transitively), listed so an
        # edit to a shared library shows up as a stale input in build_target().
        includes=(
            "shared/branches.inc",
            "shared/branch_tests.asm",
            "shared/math.inc",
            "shared/math_tests.asm",
            "shared/hw_limits.inc",
        ),
    )

    # New targets are just data:
    #
    # "game": AsmTarget(
    #     directory="fconsole/game",
    #     sources=("src/game.asm", "src/vectors.asm"),
    #     config="game.cfg",
    #     output="game.bin",
    #     start="$8000",
    #     description="Build the game image",
    #     includes=("src/common.inc",),
    # ),
}


def build_target(name: str, force: bool = False) -> None:
    t = TARGETS[name]
    d = ROOT / t.directory
    py = ensure_venv()

    common_inputs = [d / x for x in t.includes]

    for src, obj, listing in zip(t.sources, t.objects, t.listings):
        inputs = [d / src, *common_inputs]
        outputs = [d / obj, d / listing]
        if stale(outputs, inputs, force):
            print(f"Assembling {src} -> {obj} ...")
            wasi(
                py, "ca65",
                "--cpu", t.cpu,
                "--debug-info",
                "--listing", listing,
                "--segment-list",
                "--list-bytes", "16",
                "--expand-macros",
                "-o", obj,
                src,
                cwd=d,
            )
        else:
            print(f"  up to date: {obj}")

    link_inputs = [d / x for x in (*t.objects, t.config)]
    link_outputs = [d / x for x in (t.output, t.map, t.dbg, t.labels)]
    if stale(link_outputs, link_inputs, force):
        print(f"Linking {t.output} ...")
        wasi(
            py, "ld65",
            "-C", t.config,
            "--mapfile", t.map,
            "--dbgfile", t.dbg,
            "-Ln", t.labels,
            "-vm",
            "-o", t.output,
            *t.objects,
            cwd=d,
        )
    else:
        print(f"  up to date: {t.output}")

    if stale([d / t.disasm], [d / t.output], force):
        print(f"Disassembling {t.output} -> {t.disasm} ...")
        wasi(
            py, "da65",
            "--cpu", t.cpu,
            "--start-addr", t.start,
            "--multi-pass",
            "-o", t.disasm,
            t.output,
            cwd=d,
        )
    else:
        print(f"  up to date: {t.disasm}")

    print(f"{name} build complete.")


def clean_target(name: str) -> None:
    t = TARGETS[name]
    d = ROOT / t.directory
    artifacts = (
        *t.objects, *t.listings,
        t.output, t.map, t.dbg, t.labels, t.disasm,
    )
    for rel in artifacts:
        p = d / rel
        if p.is_file():
            p.unlink()
            print(f"  rm {p.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# Project commands
# ---------------------------------------------------------------------------

def cmd_build(args: argparse.Namespace) -> None:
    build_target(args.target, args.force)


def cmd_all(args: argparse.Namespace) -> None:
    for name in TARGETS:
        build_target(name, args.force)


def cmd_clean(args: argparse.Namespace) -> None:
    # Every target's outputs are declared in its AsmTarget, so no per-file
    # leftovers are hardcoded here (kept parallel with the kernel-side driver).
    targets = tuple(args.targets) if args.targets else tuple(TARGETS)
    unknown = [t for t in targets if t not in TARGETS]
    if unknown:
        raise SystemExit(
            f"build.py: unknown target(s) {unknown}; choose from {tuple(TARGETS)}"
        )
    for name in targets:
        clean_target(name)

    print("Clean complete.")


def cmd_run(args: argparse.Namespace) -> None:
    """Build the host image and launch it inside the emulator.

    The host .bin is self-describing (4-byte {load_addr, start_ptr} header at
    file offset 0, written by the VECTORS segment of fconsole.asm).  It is
    loaded into user space via --load; the raw BIOS image stays on the
    kernel side of that boundary and is configured by the emulator itself.
    """
    build_target("fconsole")
    py = ensure_venv()
    bin_path = ROOT / "hosts" / "fconsole.bin"
    fcon_args = [
        "--clock-hz", str(args.clock_hz),
        "--instructions-per-batch", str(args.instructions_per_batch),
        "--screen-scale", str(args.screen_scale),
        "--video-backend", args.video_backend,
        "--refresh-hz", str(args.refresh_hz),
        "--load", str(bin_path),
        *args.extra,
    ]
    print(f"Running fcon.py with: {' '.join(str(a) for a in fcon_args)}")
    r = run(py, "fcon.py", *fcon_args, cwd=FCON_DIR, check=False)
    raise SystemExit(r.returncode)


def cmd_macro_tests(_: argparse.Namespace) -> None:
    """Build the host test image and run it headless under the real BIOS.

    Exit code contract (run_headless.py):
      0 PASSED   - HALTED reached with no failures
      1 FAILED   - a test reported failure before freezing
      2 FROZEN   - frozen without FAIL flags set
      3 TIMEOUT  - still running after STEP_LIMIT steps
    """
    build_target("fconsole")
    py = ensure_venv()
    runner = ROOT / "headless-run" / "run_headless.py"
    r = run(
        py, runner, str(ROOT / "hosts" / "fconsole.bin"),
        cwd=ROOT, capture=True, check=False,
    )
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    if r.returncode == 0:
        print("\nmacro-tests: PASSED")
    elif r.returncode in (1, 2):
        print(f"\nmacro-tests: failed (exit {r.returncode})")
    else:
        print(f"\nmacro-tests: timed out or unexpected exit ({r.returncode})")
    raise SystemExit(r.returncode)


def cmd_lint(_: argparse.Namespace) -> None:
    # User-land tree only; the kernel/emulator tree has its own driver.
    ensure_venv()
    run(venv_tool("ruff"), "check", ".", "--fix", cwd=ROOT)
    run(venv_tool("pyrefly"), "check", ".", cwd=ROOT)


def cmd_format(_: argparse.Namespace) -> None:
    ensure_venv()
    run(venv_tool("ruff"), "format", ".", cwd=ROOT)


def cmd_format_asm(_: argparse.Namespace) -> None:
    py = ensure_venv()
    fmt = ROOT / ".." / "dev-tools" / "fmt6502" / "fmt6502.py"

    # Format every .asm source under the app/ directory, including files
    # nested in subdirectories (e.g. hosts/shared/).  Generated
    # disassemblies (*.disasm.asm) are skipped.
    root = ROOT
    skip_dirs = {".git", "venv", "__pycache__"}
    files = sorted(
        p for p in root.rglob("*.asm")
        if p.is_file()
        and not p.name.endswith(".disasm.asm")
        and not any(part in skip_dirs for part in p.relative_to(root).parts)
    )

    if not files:
        print("No assembly files found.")
        return

    print(f"Formatting {len(files)} assembly file(s):")
    for p in files:
        print(f"  {p.relative_to(root)}")

    # NOTE: --strict is intentionally omitted.  Some .asm sources use macro
    # parameters as opcodes (e.g. branch_tests.asm) or macros defined in
    # .inc files, which produce "unresolved macro" warnings; --strict would
    # treat those as fatal and refuse to format anything.
    run(
        py, fmt,
        "--indent-size", "4",
        "--comment-indent", "40",
        "--min-comment-gap", "2",
        "--in-place",
        *[str(p) for p in files],
        cwd=root,
    )


def cmd_typecheck(_: argparse.Namespace) -> None:
    ensure_venv()
    run(venv_tool("pyrefly"), "check", ".", cwd=ROOT)


# Python test scripts owned by this user-land tree.  Kernel-side suites
# (fmt6502, hw parser, cc65 pipeline) belong to the top-level driver and are
# deliberately NOT re-listed here.  The inc-drift check lives in the shared
# tools/ dir and verifies our mirror copies against the kernel originals.
TESTS: tuple[tuple[str, str | None], ...] = (
    ("../tools/inc_drift_check.py", None),
)


def _run_macro_tests(py: Path, failures: list[str]) -> None:
    """Build the host image and run it headless under the real BIOS."""
    print("\n--- macro tests (headless) ---", flush=True)
    build_target("fconsole")
    runner = ROOT / "headless-run" / "run_headless.py"
    r = run(
        py, runner, str(ROOT / "hosts" / "fconsole.bin"),
        cwd=ROOT, capture=True, check=False,
    )
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    if r.returncode:
        failures.append(f"macro-tests/run_headless.py (exit {r.returncode})")


def cmd_test(_: argparse.Namespace) -> None:
    py = ensure_venv()
    failures: list[str] = []

    for script, cwd in TESTS:
        print(f"\n--- {script} ---", flush=True)
        r = run(
            py, ROOT / script,
            cwd=ROOT / cwd if cwd else ROOT,
            capture=True,
            check=False,
        )
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        if r.returncode:
            failures.append(f"{script} (exit {r.returncode})")

    _run_macro_tests(py, failures)

    if failures:
        print(f"\n{len(failures)} test suite(s) failed:")
        for failure in failures:
            print(f"  FAIL  {failure}")
        raise SystemExit(1)

    print("\nAll test suites passed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

RUN_PRESETS = {
    "run-text": ("text", 60, "Run with native Tk text renderer"),
    "run-tk": ("tk", 30, "Run with Tk bitmap renderer"),
    "run-pygame": ("pygame", 60, "Run with pygame renderer"),
}


def add_force(p: argparse.ArgumentParser) -> None:
    p.add_argument("-f", "--force", action="store_true",
                   help="rebuild even when outputs are up to date")


def add_run_args(p: argparse.ArgumentParser, backend: str,
                 refresh: float, configurable: bool) -> None:
    p.add_argument("--clock-hz", type=float, default=1_000_000)
    p.add_argument("--instructions-per-batch", type=int, default=2_000)
    p.add_argument("--screen-scale", type=int, default=4)
    p.add_argument("--refresh-hz", type=float, default=refresh)
    if configurable:
        p.add_argument("--video-backend", choices=("tk", "text", "pygame"),
                       default=backend)
    else:
        p.set_defaults(video_backend=backend)
    p.add_argument("extra", nargs="*", default=[],
                   help="arguments forwarded to fcon.py; use -- first")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="yahtzee-a8 cross-platform build script"
    )
    sp = p.add_subparsers(dest="command", required=True)

    # Every entry in TARGETS automatically becomes a CLI command.
    for name, target in TARGETS.items():
        sub = sp.add_parser(name, help=target.description)
        add_force(sub)
        sub.set_defaults(func=cmd_build, target=name)

    sub = sp.add_parser("all", help="Build all assembly targets")
    add_force(sub)
    sub.set_defaults(func=cmd_all)

    sub = sp.add_parser("clean", help="Remove build artifacts")
    # No choices= here: on Python < 3.11 an empty explicit list trips choice
    # validation for a plain "clean". Unknown names are checked at run time in
    # cmd_clean with an equivalent message.
    sub.add_argument("targets", nargs="*",
                     help="targets to clean; default: all")
    sub.set_defaults(func=cmd_clean)

    run_p = sp.add_parser("run", help="Build BIOS and run the emulator")
    add_run_args(run_p, "pygame", 60, True)
    run_p.set_defaults(func=cmd_run)

    for name, (backend, refresh, help_text) in RUN_PRESETS.items():
        sub = sp.add_parser(name, help=help_text)
        add_run_args(sub, backend, refresh, False)
        sub.set_defaults(func=cmd_run)

    sub = sp.add_parser(
        "macro-tests",
        help="Build host test image and run it headless under the BIOS",
    )
    sub.set_defaults(func=cmd_macro_tests)

    for name, help_text, func in (
        ("lint", "Run ruff + pyrefly", cmd_lint),
        ("format", "Format Python sources", cmd_format),
        ("format-asm", "Format assembly sources", cmd_format_asm),
        ("typecheck", "Type-check Python sources", cmd_typecheck),
        ("test", "Run all known test suites", cmd_test),
    ):
        sp.add_parser(name, help=help_text).set_defaults(func=func)

    return p


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
