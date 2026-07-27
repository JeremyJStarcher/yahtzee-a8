#!/usr/bin/env python3
"""Build original and formatted ca65 projects and compare semantic artifacts."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from fmt6502 import FormatDiagnostic, format_sources


_DEFAULT_EXTENSIONS = frozenset({".asm", ".inc"})
_EXPORT_RE = re.compile(
    r"(?P<name>[A-Za-z_@.?][A-Za-z0-9_@.?$]*)"
    r"\s+(?P<address>[0-9A-Fa-f]{4,8})\s+\S+"
)


class VerificationError(RuntimeError):
    """Raised when the equivalence run cannot be completed safely."""


@dataclass(frozen=True)
class ArtifactComparison:
    """Comparison details for one generated build artifact."""

    relative_path: str
    original_size: int
    formatted_size: int
    original_sha256: str
    formatted_sha256: str
    first_difference: int | None

    @property
    def matches(self) -> bool:
        return self.first_difference is None and self.original_size == self.formatted_size


def _read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _source_paths(root: Path, extensions: frozenset[str]) -> list[Path]:
    paths = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in extensions
    ]
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def _format_project(
    root: Path,
    *,
    extensions: frozenset[str],
    strict: bool,
) -> tuple[int, tuple[FormatDiagnostic, ...]]:
    paths = _source_paths(root, extensions)
    if not paths:
        wanted = ", ".join(sorted(extensions))
        raise VerificationError(f"no source files with extensions {wanted} under {root}")

    sources: dict[str, str] = {
        path.relative_to(root).as_posix(): _read_text(path) for path in paths
    }
    results = format_sources(sources, strict=False)
    diagnostics = tuple(
        diagnostic
        for relative_path in sorted(results)
        for diagnostic in results[relative_path].diagnostics
    )

    errors = [item for item in diagnostics if item.severity == "error"]
    if errors or (strict and diagnostics):
        reason = "formatter errors" if errors else "strict formatter diagnostics"
        rendered = "\n".join(item.render() for item in diagnostics)
        raise VerificationError(f"{reason} prevent equivalence validation:\n{rendered}")

    changed = 0
    formatted_sources: dict[str, str] = {}
    for relative_path, source in sources.items():
        result = results[relative_path]
        if len(source.splitlines()) != len(result.text.splitlines()):
            raise VerificationError(f"formatter changed line count in {relative_path}")
        formatted_sources[relative_path] = result.text
        if result.text != source:
            _write_text(root / relative_path, result.text)
            changed += 1

    second_pass = format_sources(formatted_sources, strict=False)
    unstable = [
        relative_path
        for relative_path, result in second_pass.items()
        if result.text != formatted_sources[relative_path]
    ]
    if unstable:
        detail = ", ".join(unstable)
        raise VerificationError(f"formatter is not idempotent for: {detail}")

    return changed, diagnostics


def _run_build(root: Path, command: str, variant: str) -> None:
    print(f"[{variant}] $ {command}")
    environment = os.environ.copy()
    environment["FMT6502_BUILD_VARIANT"] = variant
    completed = subprocess.run(
        command,
        cwd=root,
        env=environment,
        shell=True,
        check=False,
    )
    if completed.returncode != 0:
        raise VerificationError(
            f"{variant} build failed with exit status {completed.returncode}"
        )


def _safe_relative_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise VerificationError(
            f"artifact path escapes the project root: {relative_path}"
        ) from exc
    return candidate


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _first_difference(left: bytes, right: bytes) -> int | None:
    for index, (left_byte, right_byte) in enumerate(zip(left, right)):
        if left_byte != right_byte:
            return index
    if len(left) != len(right):
        return min(len(left), len(right))
    return None


def _compare_artifact(
    original_root: Path,
    formatted_root: Path,
    relative_path: str,
) -> ArtifactComparison:
    original_path = _safe_relative_path(original_root, relative_path)
    formatted_path = _safe_relative_path(formatted_root, relative_path)
    if not original_path.is_file():
        raise VerificationError(f"original build did not create {relative_path}")
    if not formatted_path.is_file():
        raise VerificationError(f"formatted build did not create {relative_path}")

    original = original_path.read_bytes()
    formatted = formatted_path.read_bytes()
    return ArtifactComparison(
        relative_path=relative_path,
        original_size=len(original),
        formatted_size=len(formatted),
        original_sha256=_sha256(original),
        formatted_sha256=_sha256(formatted),
        first_difference=_first_difference(original, formatted),
    )


def _parse_exports(path: Path) -> dict[str, int]:
    lines = _read_text(path).splitlines()
    start = next(
        (index + 1 for index, line in enumerate(lines) if line.strip() == "Exports list by name:"),
        None,
    )
    if start is None:
        raise VerificationError(f"cannot find 'Exports list by name' in {path}")

    exports: dict[str, int] = {}
    saw_entry = False
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped or set(stripped) == {"-"}:
            if saw_entry and not stripped:
                break
            continue
        matches = list(_EXPORT_RE.finditer(line))
        if not matches:
            if saw_entry:
                break
            continue
        saw_entry = True
        for match in matches:
            exports[match.group("name")] = int(match.group("address"), 16)

    if not exports:
        raise VerificationError(f"no exports parsed from {path}")
    return exports


def _compare_exports(
    original_root: Path,
    formatted_root: Path,
    map_file: str,
    requested: Sequence[str],
) -> tuple[bool, Mapping[str, int], list[str]]:
    original_path = _safe_relative_path(original_root, map_file)
    formatted_path = _safe_relative_path(formatted_root, map_file)
    if not original_path.is_file() or not formatted_path.is_file():
        raise VerificationError(f"both builds must create map file {map_file}")

    original = _parse_exports(original_path)
    formatted = _parse_exports(formatted_path)
    names = sorted(set(requested) if requested else set(original) | set(formatted))
    differences: list[str] = []
    stable: dict[str, int] = {}
    for name in names:
        left = original.get(name)
        right = formatted.get(name)
        if left is None:
            differences.append(f"{name}: absent from original map")
        elif right is None:
            differences.append(f"{name}: absent from formatted map")
        elif left != right:
            differences.append(f"{name}: original ${left:04X}, formatted ${right:04X}")
        else:
            stable[name] = left
    return not differences, stable, differences


def _parse_int(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer: {value}") from exc


def _parse_vector(value: str) -> tuple[str, int]:
    name, separator, address = value.partition("=")
    if not separator or not name.strip() or not address.strip():
        raise argparse.ArgumentTypeError("vector must use NAME=ADDRESS")
    return name.strip(), _parse_int(address.strip())


def _read_vector(rom: bytes, *, rom_base: int, address: int) -> int:
    offset = address - rom_base
    if offset < 0 or offset + 1 >= len(rom):
        raise VerificationError(
            f"vector address ${address:04X} is outside ROM image based at ${rom_base:04X}"
        )
    return rom[offset] | (rom[offset + 1] << 8)


def _print_mismatch(comparison: ArtifactComparison) -> None:
    print(f"MISMATCH: {comparison.relative_path}")
    print(
        f"  sizes: original={comparison.original_size}, "
        f"formatted={comparison.formatted_size}"
    )
    if comparison.first_difference is not None:
        print(f"  first differing offset: 0x{comparison.first_difference:X}")
    print(f"  original sha256:  {comparison.original_sha256}")
    print(f"  formatted sha256: {comparison.formatted_sha256}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", help="project directory copied for both builds")
    parser.add_argument(
        "--build-command",
        required=True,
        help="shell command run in each project copy, for example 'make clean all'",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        required=True,
        metavar="PATH",
        help="relative generated file to compare byte-for-byte; repeat as needed",
    )
    parser.add_argument(
        "--map-file",
        metavar="PATH",
        help="optional ld65 map file whose exported symbols must remain unchanged",
    )
    parser.add_argument(
        "--export",
        action="append",
        default=[],
        metavar="SYMBOL",
        help="export to verify in --map-file; omit to compare every export",
    )
    parser.add_argument(
        "--rom-base",
        type=_parse_int,
        help="load address of the first artifact, required with --vector",
    )
    parser.add_argument(
        "--vector",
        action="append",
        type=_parse_vector,
        default=[],
        metavar="NAME=ADDRESS",
        help="decode and report a little-endian vector from the first artifact",
    )
    parser.add_argument(
        "--source-extension",
        action="append",
        default=[],
        metavar="EXT",
        help="source extension to format; defaults to .asm and .inc",
    )
    parser.add_argument(
        "--strict-format",
        action="store_true",
        help="abort when the formatter reports any warning or error",
    )
    parser.add_argument(
        "--keep-worktree",
        action="store_true",
        help="retain the original and formatted project copies for inspection",
    )
    parser.add_argument(
        "--work-root",
        metavar="DIR",
        help="directory in which to create original/ and formatted/ copies",
    )
    return parser


def _prepare_work_root(args: argparse.Namespace) -> tuple[Path, bool]:
    if args.work_root:
        work_root = Path(args.work_root).expanduser().resolve()
        if work_root.exists() and any(work_root.iterdir()):
            raise VerificationError(f"work root is not empty: {work_root}")
        work_root.mkdir(parents=True, exist_ok=True)
        return work_root, False
    return Path(tempfile.mkdtemp(prefix="fmt6502-equivalence-")), True


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        print(f"verify-build: project directory not found: {project_root}", file=sys.stderr)
        return 2
    if args.vector and args.rom_base is None:
        print("verify-build: --rom-base is required with --vector", file=sys.stderr)
        return 2
    if args.export and not args.map_file:
        print("verify-build: --export requires --map-file", file=sys.stderr)
        return 2

    extensions = frozenset(
        (item if item.startswith(".") else "." + item).lower()
        for item in (args.source_extension or _DEFAULT_EXTENSIONS)
    )

    work_root: Path | None = None
    temporary = False
    try:
        work_root, temporary = _prepare_work_root(args)
        try:
            work_root.relative_to(project_root)
        except ValueError:
            pass
        else:
            raise VerificationError("work root must be outside the project tree")

        original_root = work_root / "original"
        formatted_root = work_root / "formatted"
        shutil.copytree(project_root, original_root)
        shutil.copytree(project_root, formatted_root)

        _run_build(original_root, args.build_command, "original")
        changed, diagnostics = _format_project(
            formatted_root,
            extensions=extensions,
            strict=args.strict_format,
        )
        print(
            f"[formatted] formatter changed {changed} of "
            f"{len(_source_paths(formatted_root, extensions))} source files"
        )
        for diagnostic in diagnostics:
            print(diagnostic.render(), file=sys.stderr)
        _run_build(formatted_root, args.build_command, "formatted")

        equivalent = True
        comparisons: list[ArtifactComparison] = []
        for artifact in args.artifact:
            comparison = _compare_artifact(original_root, formatted_root, artifact)
            comparisons.append(comparison)
            if comparison.matches:
                print(
                    f"MATCH: {artifact} ({comparison.original_size} bytes, "
                    f"sha256 {comparison.original_sha256})"
                )
            else:
                equivalent = False
                _print_mismatch(comparison)

        if args.map_file:
            exports_match, stable_exports, differences = _compare_exports(
                original_root,
                formatted_root,
                args.map_file,
                args.export,
            )
            if exports_match:
                print(f"MATCH: exports in {args.map_file}")
                for name, address in stable_exports.items():
                    print(f"  {name} = ${address:04X}")
            else:
                equivalent = False
                print(f"MISMATCH: exports in {args.map_file}")
                for difference in differences:
                    print(f"  {difference}")

        if args.vector:
            original_rom = _safe_relative_path(
                original_root, comparisons[0].relative_path
            ).read_bytes()
            formatted_rom = _safe_relative_path(
                formatted_root, comparisons[0].relative_path
            ).read_bytes()
            print("Vector table:")
            for name, address in args.vector:
                original_target = _read_vector(
                    original_rom, rom_base=args.rom_base, address=address
                )
                formatted_target = _read_vector(
                    formatted_rom, rom_base=args.rom_base, address=address
                )
                marker = "MATCH" if original_target == formatted_target else "MISMATCH"
                print(
                    f"  {marker}: {name} @ ${address:04X} -> "
                    f"original ${original_target:04X}, formatted ${formatted_target:04X}"
                )
                if original_target != formatted_target:
                    equivalent = False

        if args.keep_worktree or args.work_root:
            print(f"Worktree: {work_root}")
        return 0 if equivalent else 1
    except (OSError, UnicodeError, VerificationError) as exc:
        print(f"verify-build: {exc}", file=sys.stderr)
        if work_root is not None and (args.keep_worktree or args.work_root):
            print(f"Worktree: {work_root}", file=sys.stderr)
        return 2
    finally:
        if temporary and work_root is not None and not args.keep_worktree:
            shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
