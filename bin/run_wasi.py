#!/usr/bin/env python3
"""run_wasi.py — Generic WASI command-module launcher using embedded Wasmtime.

Usage:
    python3 run_wasi.py <tool> [tool arguments...]

Examples:
    python3 run_wasi.py ca65 --version
    python3 run_wasi.py ca65 src/bios.asm -o build/bios.o
    python3 run_wasi.py ld65 -C bios.cfg build/bios.o -o bios.bin

Tool configuration lives in tools.json (JSON, no extra dependency).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


# --- path helpers ---

def _repo_root() -> Path:
    """Absolute path to the repository root (where this script lives)."""
    return Path(__file__).resolve().parent


def _resolve_host(relative: str) -> Path:
    """Resolve a host path relative to the repository root."""
    return (_repo_root() / relative).resolve()


# --- configuration ---

def _load_tool_config(tool_name: str) -> dict[str, Any]:
    """Load the JSON configuration for the named tool."""
    config_path = _repo_root() / "tools.json"
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            registry = json.load(fh)
    except FileNotFoundError:
        _die(f"Configuration file not found: {config_path}")
    except json.JSONDecodeError as exc:
        _die(f"Invalid JSON in {config_path}: {exc}")

    tools: dict[str, Any] = registry.get("tools", {})
    if tool_name not in tools:
        known = ", ".join(sorted(tools.keys())) or "(none)"
        _die(f"Unknown tool '{tool_name}'.  Known tools: {known}")

    return tools[tool_name]


def _resolve_module(module_rel: str) -> Path:
    """Resolve the .wasm module path."""
    path = _resolve_host(module_rel)
    if not path.is_file():
        _die(f"WebAssembly module not found: {path}")
    return path


def _resolve_mounts(
    mounts: list[dict[str, Any]],
) -> list[tuple[Path, str]]:
    """Resolve host/guest mount pairs; report missing required dirs."""
    pairs: list[tuple[Path, str]] = []
    for m in mounts:
        host = _resolve_host(m["host"])
        guest = m["guest"]
        optional = m.get("optional", False)
        if not host.is_dir():
            if optional:
                continue
            _die(f"Required resource directory not found: {host}")
        pairs.append((host, guest))
    return pairs


# --- error handling ---

def _die(message: str, code: int = 1) -> None:
    print(f"run_wasi: {message}", file=sys.stderr)
    sys.exit(code)


# --- runtime ---

def _get_wasmtime() -> Any:
    """Import wasmtime, bootstrapping if necessary."""
    try:
        import wasmtime  # type: ignore[import-untyped]
        return wasmtime
    except ImportError:
        pass

    # Attempt self-bootstrap
    bootstrap_path = _repo_root() / "../bootstrap_runtime.py"
    if not bootstrap_path.is_file():
        _die(
            "The 'wasmtime' Python package is not installed and "
            "bootstrap_runtime.py was not found.  Install wasmtime-py "
            "(pip install wasmtime) or place wheels in vendor/wheels/."
        )

    # Run bootstrap as a subprocess so __name__ == "__main__" works.
    r = subprocess.run(
        [sys.executable, str(bootstrap_path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        _die(f"Bootstrap failed (exit {r.returncode}):\n{r.stderr}")

    # The bootstrap installs into .runtime/site-packages/ — add it to sys.path.
    runtime_sp = _repo_root() / ".." / ".runtime" / "site-packages"
    runtime_sp = runtime_sp.resolve()
    if runtime_sp.is_dir() and str(runtime_sp) not in sys.path:
        sys.path.insert(0, str(runtime_sp))

    import wasmtime  # type: ignore[import-untyped,no-redef]
    return wasmtime


def _run_tool(
    tool_name: str,
    tool_args: list[str],
    tool_config: dict[str, Any],
) -> int:
    """Instantiate and run the WASI module; return the guest exit code."""
    wasmtime = _get_wasmtime()

    module_path = _resolve_module(tool_config["module"])
    environment: dict[str, str] = dict(tool_config.get("environment", {}))
    mount_pairs = _resolve_mounts(tool_config.get("mounts", []))

    # --- WASI configuration ---
    wasi_config = wasmtime.WasiConfig()

    # argv
    wasi_config.argv = [tool_name, *tool_args]

    # stdio
    wasi_config.inherit_stdin()
    wasi_config.inherit_stdout()
    wasi_config.inherit_stderr()

    # environment — wasmtime-py expects an iterable of (key, value) pairs
    wasi_config.env = list(environment.items())

    # preopens — always preopen CWD as guest "."
    wasi_config.preopen_dir(str(Path.cwd()), ".")

    for host_path, guest_path in mount_pairs:
        wasi_config.preopen_dir(str(host_path), guest_path)

    # --- engine, store, linker ---
    engine = wasmtime.Engine()
    store = wasmtime.Store(engine)
    store.set_wasi(wasi_config)

    linker = wasmtime.Linker(engine)
    linker.define_wasi()

    module = wasmtime.Module.from_file(engine, str(module_path))
    instance = linker.instantiate(store, module)

    # --- execute ---
    start = instance.exports(store)["_start"]
    try:
        start(store)
    except wasmtime.WasmtimeError as exc:
        # proc_exit(N) is reported as a WasmtimeError.  Extract the
        # exit code from the message.
        # wasmtime-py v47:  "Exited with i32 exit status 0"
        # older versions:    "exited with code 1"
        import re
        msg = str(exc)
        # wasmtime-py v47:  "... Exited with i32 exit status 0"
        # older versions:    "... exited with code 1"
        match = re.search(
            r"(?:exit\s+status|exited\s+with\s+code)\s+(\d+)",
            msg, re.IGNORECASE,
        )
        if match:
            return int(match.group(1))
        _die(f"Wasm trap: {exc}")
        return 1

    return 0


# --- main ---

def main(argv: list[str]) -> int:
    if len(argv) < 2:
        _die(
            "Usage: python3 run_wasi.py <tool> [tool arguments...]\n"
            "Example: python3 run_wasi.py ca65 --version"
        )

    tool_name = argv[1]
    tool_args = argv[2:]

    tool_config = _load_tool_config(tool_name)
    return _run_tool(tool_name, tool_args, tool_config)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
