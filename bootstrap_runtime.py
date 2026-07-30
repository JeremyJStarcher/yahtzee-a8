#!/usr/bin/env python3
"""bootstrap_runtime.py — Self-bootstrap the wasmtime-py dependency.

This script is called by run_wasi.py when wasmtime is not already importable.
It tries, in order:

1. Import the pinned wasmtime package (already available).
2. Find a compatible wheel in vendor/wheels/ and install it into a private
   site-packages directory (.runtime/).
3. (Optional) Fall back to online pip install of the pinned version.

After a successful bootstrap, sys.path is extended so that a subsequent
'import wasmtime' will succeed.

Configuration lives in:

    requirements-runtime.txt    — pinned wasmtime version
    vendor/wheels/              — optional offline wheel cache
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent
_REQUIREMENTS = _REPO_ROOT / "requirements-runtime.txt"
_VENDOR_WHEELS = _REPO_ROOT / "vendor" / "wheels"
_RUNTIME_DIR = _REPO_ROOT / ".runtime"
_SITE_PACKAGES = _RUNTIME_DIR / "site-packages"


def _parse_pinned_version() -> str | None:
    """Extract the pinned wasmtime version from requirements-runtime.txt."""
    if not _REQUIREMENTS.is_file():
        return None
    for line in _REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "wasmtime" in line.lower():
            return line
    return None


def _try_import() -> bool:
    """Return True if wasmtime is already importable."""
    try:
        import wasmtime  # noqa: F401
        return True
    except ImportError:
        return False


def _extend_sys_path() -> None:
    """Add the private site-packages to sys.path if it exists."""
    if str(_SITE_PACKAGES) not in sys.path and _SITE_PACKAGES.is_dir():
        sys.path.insert(0, str(_SITE_PACKAGES))


def _install_wheel(wheel_path: Path) -> None:
    """Install a single .whl into the private site-packages."""
    _SITE_PACKAGES.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [
            sys.executable, "-m", "pip", "install",
            "--target", str(_SITE_PACKAGES),
            "--no-deps",
            str(wheel_path),
        ],
        stdout=subprocess.DEVNULL,
    )


def _install_from_vendor() -> bool:
    """Try to find and install a compatible wheel from vendor/wheels/."""
    if not _VENDOR_WHEELS.is_dir():
        return False

    wheels = sorted(_VENDOR_WHEELS.glob("wasmtime-*.whl"))
    if not wheels:
        return False

    # Use the newest (last sorted) wheel
    wheel = wheels[-1]
    print(f"run_wasi: installing bundled wasmtime wheel: {wheel.name}",
          file=sys.stderr)
    try:
        _install_wheel(wheel)
    except subprocess.CalledProcessError as exc:
        print(f"run_wasi: wheel install failed: {exc}", file=sys.stderr)
        return False

    _extend_sys_path()
    return _try_import()


def _install_online(pinned: str) -> bool:
    """Install wasmtime from PyPI using the pinned version."""
    print(f"run_wasi: installing {pinned} (online)...", file=sys.stderr)
    _SITE_PACKAGES.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.check_call(
            [
                sys.executable, "-m", "pip", "install",
                "--target", str(_SITE_PACKAGES),
                "--no-deps",
                pinned,
            ],
            stdout=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return False

    _extend_sys_path()
    return _try_import()


def main() -> int:
    # Already available?
    if _try_import():
        return 0

    # Try vendor wheels
    if _install_from_vendor():
        return 0

    # Try online
    pinned = _parse_pinned_version()
    if pinned and _install_online(pinned):
        return 0

    print(
        "run_wasi: cannot bootstrap wasmtime.  Options:\n"
        "  1. pip install wasmtime\n"
        "  2. Place a compatible .whl in vendor/wheels/\n"
        "  3. Create requirements-runtime.txt with a pinned version",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
