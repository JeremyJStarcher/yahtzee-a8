#!/usr/bin/env python3
"""Syntax-aware source formatter for ca65/cc65 6502 assembly."""

from __future__ import annotations

import argparse
import difflib
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class FormatterConfig:
    """Formatting settings."""

    indent_size: int = 4
    comment_indent: int = 40
    min_comment_gap: int = 2
    tab_width: int = 8

    def __post_init__(self) -> None:
        if self.indent_size < 0:
            raise ValueError("indent_size must be non-negative")
        if self.comment_indent < 0:
            raise ValueError("comment_indent must be non-negative")
        if self.min_comment_gap < 1:
            raise ValueError("min_comment_gap must be at least 1")
        if self.tab_width < 1:
            raise ValueError("tab_width must be at least 1")


DEFAULT_CONFIG = FormatterConfig()


@dataclass(frozen=True)
class FormatDiagnostic:
    """A formatter warning or error."""

    line: int
    message: str
    severity: str = "warning"
    filename: str | None = None

    def render(self) -> str:
        location = self.filename or "<text>"
        if self.line:
            location += f":{self.line}"
        return f"{location}: {self.severity}: {self.message}"


@dataclass(frozen=True)
class FormatResult:
    """Formatted text plus diagnostics and changed line numbers."""

    text: str
    diagnostics: tuple[FormatDiagnostic, ...]
    changed_lines: tuple[int, ...]


class FormatError(ValueError):
    """Raised by strict mode when formatting is not provably safe."""

    def __init__(self, diagnostics: Sequence[FormatDiagnostic]):
        self.diagnostics = tuple(diagnostics)
        super().__init__("\n".join(item.render() for item in self.diagnostics))


@dataclass(frozen=True)
class _LexedLine:
    code: str
    comment: str | None
    normal_mask: tuple[bool, ...]
    error: str | None = None


@dataclass(frozen=True)
class _LineStructure:
    operation_span: tuple[int, int] | None
    definition_name_span: tuple[int, int] | None
    assignment: bool = False


@dataclass(frozen=True)
class _Definition:
    name: str
    filename: str | None
    line: int


@dataclass(frozen=True)
class _SymbolRegistry:
    safe_names: Mapping[str, str]
    collisions: frozenset[str]
    diagnostics: tuple[FormatDiagnostic, ...]


# The 56 documented NMOS MOS 6502 mnemonics.
NMOS_OPCODES = frozenset({
    "ADC", "AND", "ASL", "BCC", "BCS", "BEQ", "BIT", "BMI",
    "BNE", "BPL", "BRK", "BVC", "BVS", "CLC", "CLD", "CLI",
    "CLV", "CMP", "CPX", "CPY", "DEC", "DEX", "DEY", "EOR",
    "INC", "INX", "INY", "JMP", "JSR", "LDA", "LDX", "LDY",
    "LSR", "NOP", "ORA", "PHA", "PHP", "PLA", "PLP", "ROL",
    "ROR", "RTI", "RTS", "SBC", "SEC", "SED", "SEI", "STA",
    "STX", "STY", "TAX", "TAY", "TSX", "TXA", "TXS", "TYA",
})

# Useful for a more precise diagnostic. These are not formatted as NMOS opcodes.
_NON_NMOS_MNEMONICS = frozenset({
    "BRA", "PHX", "PHY", "PLX", "PLY", "STZ", "TRB", "TSB",
    "LAX", "SAX", "DCP", "ISC", "ISB", "SLO", "RLA", "RRA", "SRE",
    "WAI", "STP", "COP", "REP", "SEP", "XBA", "XCE", "MVN", "MVP",
})

# Directives that define operation-position aliases. `.macro` is the main case;
# `.define` is included because ca65 substitutions are also case-sensitive.
_DEFINITION_DIRECTIVES = frozenset({".macro", ".define"})

_IDENTIFIER = r"[A-Za-z_@.?][A-Za-z0-9_@.?$]*"
_SCOPED_IDENTIFIER = rf"{_IDENTIFIER}(?:::{_IDENTIFIER})*"
_ASSIGNMENT_RE = re.compile(rf"(?:{_SCOPED_IDENTIFIER}|\*)\s*(?::=|=)")
_LABEL_RE = re.compile(rf"{_SCOPED_IDENTIFIER}\s*:(?!:)")


def _split_line_ending(raw: str) -> tuple[str, str]:
    if raw.endswith("\r\n"):
        return raw[:-2], "\r\n"
    if raw.endswith("\n") or raw.endswith("\r"):
        return raw[:-1], raw[-1:]
    return raw, ""


def _iter_raw_lines(text: str) -> list[str]:
    """Split text while preserving LF, CRLF, CR, and a final unterminated line."""
    if not text:
        return []
    return text.splitlines(keepends=True)


def _lex_line(content: str) -> _LexedLine:
    """Split code from comment and mark characters outside quoted literals."""
    mask: list[bool] = []
    state = "normal"
    quote_start = -1
    i = 0

    while i < len(content):
        ch = content[i]

        if state == "normal":
            if ch == ";":
                return _LexedLine(
                    code=content[:i],
                    comment=content[i:],
                    normal_mask=tuple(mask),
                )
            if ch == '"':
                state = "double"
                quote_start = i
                mask.append(False)
                i += 1
                continue
            if ch == "'":
                state = "single"
                quote_start = i
                mask.append(False)
                i += 1
                continue
            mask.append(True)
            i += 1
            continue

        mask.append(False)

        # Backslash escapes the following character within either quote style.
        if ch == "\\":
            i += 1
            if i < len(content):
                mask.append(False)
                i += 1
            continue

        expected = '"' if state == "double" else "'"
        if ch == expected:
            # Accept doubled quotes as a literal quote and remain in the string.
            if i + 1 < len(content) and content[i + 1] == expected:
                mask.append(False)
                i += 2
                continue
            state = "normal"
        i += 1

    if state != "normal":
        style = "double" if state == "double" else "single"
        return _LexedLine(
            code=content,
            comment=None,
            normal_mask=tuple(mask),
            error=f"unterminated {style}-quoted literal beginning at offset {quote_start}",
        )

    return _LexedLine(code=content, comment=None, normal_mask=tuple(mask))


def _masked_code(code: str, normal_mask: Sequence[bool]) -> str:
    return "".join(ch if is_normal else " " for ch, is_normal in zip(code, normal_mask))


def _next_token_span(masked: str, start: int) -> tuple[int, int] | None:
    i = start
    while i < len(masked) and masked[i].isspace():
        i += 1
    if i >= len(masked):
        return None
    j = i
    while j < len(masked) and not masked[j].isspace():
        j += 1
    return i, j


def _parse_structure(code: str, normal_mask: Sequence[bool]) -> _LineStructure:
    masked = _masked_code(code, normal_mask)
    start = 0
    while start < len(masked) and masked[start].isspace():
        start += 1
    if start >= len(masked):
        return _LineStructure(None, None)

    assignment_match = _ASSIGNMENT_RE.match(masked, start)
    if assignment_match:
        return _LineStructure(None, None, assignment=True)

    # A colon by itself is ca65's anonymous-label form.
    if masked[start] == ":" and not masked.startswith("::", start):
        start += 1
    else:
        label_match = _LABEL_RE.match(masked, start)
        if label_match:
            start = label_match.end()

    operation_span = _next_token_span(masked, start)
    if operation_span is None:
        return _LineStructure(None, None)

    op_start, op_end = operation_span
    operation = code[op_start:op_end].lower()
    definition_span = None
    if operation in _DEFINITION_DIRECTIVES:
        definition_span = _next_token_span(masked, op_end)
        if definition_span is not None:
            ds, de = definition_span
            # Macro parameter separators are not part of the definition name.
            comma = code.find(",", ds, de)
            if comma != -1:
                definition_span = (ds, comma)

    return _LineStructure(operation_span, definition_span)


def _discover_definitions(
    sources: Mapping[str | None, str],
) -> _SymbolRegistry:
    definitions: dict[str, list[_Definition]] = {}
    diagnostics: list[FormatDiagnostic] = []

    for filename, text in sources.items():
        for lineno, raw in enumerate(_iter_raw_lines(text), start=1):
            body, _ = _split_line_ending(raw)
            content = body.lstrip(" \t")
            if not content or content.startswith(";"):
                continue
            lexed = _lex_line(content)
            if lexed.error:
                # The formatting pass reports malformed lines exactly once and
                # returns them unchanged. Discovery simply skips them.
                continue
            structure = _parse_structure(lexed.code, lexed.normal_mask)
            if structure.definition_name_span is None:
                continue
            start, end = structure.definition_name_span
            name = lexed.code[start:end]
            if not name:
                diagnostics.append(FormatDiagnostic(
                    filename=filename,
                    line=lineno,
                    severity="error",
                    message="macro or alias definition is missing a name",
                ))
                continue
            definitions.setdefault(name.casefold(), []).append(
                _Definition(name=name, filename=filename, line=lineno)
            )

    safe_names: dict[str, str] = {}
    collisions: set[str] = set()
    for folded, items in definitions.items():
        spellings = {item.name for item in items}
        if len(spellings) == 1:
            safe_names[folded] = next(iter(spellings)).lower()
            continue
        collisions.add(folded)
        detail = ", ".join(sorted(spellings))
        for item in items:
            diagnostics.append(FormatDiagnostic(
                filename=item.filename,
                line=item.line,
                severity="error",
                message=f"case-folding collision among definitions: {detail}",
            ))

    return _SymbolRegistry(
        safe_names=safe_names,
        collisions=frozenset(collisions),
        diagnostics=tuple(diagnostics),
    )


def _apply_replacements(code: str, replacements: Iterable[tuple[int, int, str]]) -> str:
    result = code
    for start, end, replacement in sorted(replacements, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result


def _normalize_commas(code: str) -> str:
    """Normalize commas only while outside quoted literals."""
    out: list[str] = []
    state = "normal"
    i = 0

    while i < len(code):
        ch = code[i]

        if state == "normal":
            if ch == '"':
                state = "double"
                out.append(ch)
                i += 1
                continue
            if ch == "'":
                state = "single"
                out.append(ch)
                i += 1
                continue
            if ch == ",":
                while out and out[-1] in (" ", "\t"):
                    out.pop()
                out.append(",")
                i += 1
                while i < len(code) and code[i] in (" ", "\t"):
                    i += 1
                if i < len(code):
                    out.append(" ")
                continue
            out.append(ch)
            i += 1
            continue

        out.append(ch)
        if ch == "\\":
            i += 1
            if i < len(code):
                out.append(code[i])
                i += 1
            continue

        expected = '"' if state == "double" else "'"
        if ch == expected:
            if i + 1 < len(code) and code[i + 1] == expected:
                out.append(code[i + 1])
                i += 2
                continue
            state = "normal"
        i += 1

    return "".join(out)


def _visual_width(text: str, tab_width: int) -> int:
    column = 0
    for ch in text:
        if ch == "\t":
            column += tab_width - (column % tab_width)
        else:
            column += 1
    return column


def _format_body(
    body: str,
    *,
    lineno: int,
    filename: str | None,
    previous_indented: bool | None,
    registry: _SymbolRegistry,
    config: FormatterConfig,
) -> tuple[str, bool | None, tuple[FormatDiagnostic, ...]]:
    """Format one line body and return (body, indentation state, diagnostics)."""
    if not body.strip(" \t"):
        return body.rstrip(" \t"), previous_indented, ()

    original_indented = len(body) != len(body.lstrip(" \t"))
    content = body.lstrip(" \t")
    lexed = _lex_line(content)

    if lexed.error:
        diagnostic = FormatDiagnostic(
            filename=filename,
            line=lineno,
            severity="error",
            message=lexed.error,
        )
        # An unsafe line is returned byte-for-byte unchanged.
        return body, previous_indented, (diagnostic,)

    code_is_empty = not lexed.code.strip(" \t")
    if code_is_empty and lexed.comment is not None:
        indented = original_indented if previous_indented is None else previous_indented
        prefix = " " * config.indent_size if indented else ""
        return prefix + lexed.comment, indented, ()

    structure = _parse_structure(lexed.code, lexed.normal_mask)
    replacements: list[tuple[int, int, str]] = []
    diagnostics: list[FormatDiagnostic] = []

    if structure.operation_span is not None:
        op_start, op_end = structure.operation_span
        operation = lexed.code[op_start:op_end]
        upper = operation.upper()
        lower = operation.lower()

        if upper in NMOS_OPCODES:
            replacements.append((op_start, op_end, upper))
        elif lower.startswith("."):
            replacements.append((op_start, op_end, lower))
        else:
            folded = operation.casefold()
            if folded in registry.collisions:
                diagnostics.append(FormatDiagnostic(
                    filename=filename,
                    line=lineno,
                    severity="error",
                    message=f"operation {operation!r} has a case-folding definition collision; casing preserved",
                ))
            elif folded in registry.safe_names:
                replacements.append((op_start, op_end, registry.safe_names[folded]))
            elif upper in _NON_NMOS_MNEMONICS:
                diagnostics.append(FormatDiagnostic(
                    filename=filename,
                    line=lineno,
                    severity="warning",
                    message=f"{operation!r} is not a documented NMOS 6502 opcode; casing preserved",
                ))
            else:
                diagnostics.append(FormatDiagnostic(
                    filename=filename,
                    line=lineno,
                    severity="warning",
                    message=f"unresolved macro or alias operation {operation!r}; casing preserved",
                ))

    if structure.definition_name_span is not None:
        name_start, name_end = structure.definition_name_span
        name = lexed.code[name_start:name_end]
        folded = name.casefold()
        if folded in registry.safe_names:
            replacements.append((name_start, name_end, registry.safe_names[folded]))
        elif folded in registry.collisions:
            # The discovery pass already emitted a precise diagnostic.
            pass

    formatted_code = _apply_replacements(lexed.code, replacements)
    formatted_code = _normalize_commas(formatted_code).rstrip(" \t")

    indent = " " * config.indent_size if original_indented else ""
    final_code = indent + formatted_code

    if lexed.comment is None:
        return final_code, original_indented, tuple(diagnostics)

    width = _visual_width(final_code, config.tab_width)
    if width < config.comment_indent:
        gap = " " * (config.comment_indent - width)
    else:
        gap = " " * config.min_comment_gap
    return final_code + gap + lexed.comment, original_indented, tuple(diagnostics)


def _format_with_registry(
    text: str,
    *,
    filename: str | None,
    registry: _SymbolRegistry,
    config: FormatterConfig,
) -> FormatResult:
    output: list[str] = []
    diagnostics: list[FormatDiagnostic] = []
    changed_lines: list[int] = []
    previous_indented: bool | None = None

    for lineno, raw in enumerate(_iter_raw_lines(text), start=1):
        body, ending = _split_line_ending(raw)
        formatted, new_previous, line_diagnostics = _format_body(
            body,
            lineno=lineno,
            filename=filename,
            previous_indented=previous_indented,
            registry=registry,
            config=config,
        )
        if formatted != body:
            changed_lines.append(lineno)
        diagnostics.extend(line_diagnostics)
        output.append(formatted + ending)
        previous_indented = new_previous

    return FormatResult(
        text="".join(output),
        diagnostics=tuple(diagnostics),
        changed_lines=tuple(changed_lines),
    )


def format_text_with_diagnostics(
    text: str,
    *,
    filename: str | None = None,
    config: FormatterConfig = DEFAULT_CONFIG,
    strict: bool = False,
) -> FormatResult:
    """Format a complete source string and retain all safety diagnostics."""
    registry = _discover_definitions({filename: text})
    result = _format_with_registry(
        text,
        filename=filename,
        registry=registry,
        config=config,
    )
    diagnostics = registry.diagnostics + result.diagnostics
    result = FormatResult(result.text, diagnostics, result.changed_lines)
    if strict and diagnostics:
        raise FormatError(diagnostics)
    return result


def format_sources(
    sources: Mapping[str, str],
    *,
    config: FormatterConfig = DEFAULT_CONFIG,
    strict: bool = False,
) -> dict[str, FormatResult]:
    """Format several files using one shared macro/alias discovery pass."""
    registry = _discover_definitions(sources)
    results: dict[str, FormatResult] = {}

    for filename, text in sources.items():
        item = _format_with_registry(
            text,
            filename=filename,
            registry=registry,
            config=config,
        )
        own_discovery = tuple(
            diagnostic for diagnostic in registry.diagnostics
            if diagnostic.filename == filename
        )
        results[filename] = FormatResult(
            text=item.text,
            diagnostics=own_discovery + item.diagnostics,
            changed_lines=item.changed_lines,
        )

    if strict:
        all_diagnostics = [
            diagnostic
            for result in results.values()
            for diagnostic in result.diagnostics
        ]
        if all_diagnostics:
            raise FormatError(all_diagnostics)

    return results


def format_line(
    line: str,
    *,
    previous_indented: bool | None = None,
    config: FormatterConfig = DEFAULT_CONFIG,
) -> tuple[str, bool]:
    """
    Format one line and return ``(formatted_body, changed)``.

    File-level macro resolution is necessarily limited for this convenience API.
    Macro definitions on the line are still normalized safely; unresolved calls
    retain their original casing. Use :func:`format_text` or :func:`format_sources`
    for normal operation.
    """
    body, _ = _split_line_ending(line)
    registry = _discover_definitions({None: body})
    formatted, _, _ = _format_body(
        body,
        lineno=1,
        filename=None,
        previous_indented=previous_indented,
        registry=registry,
        config=config,
    )
    return formatted, formatted != body


def format_text(
    text: str,
    *,
    config: FormatterConfig = DEFAULT_CONFIG,
    strict: bool = False,
) -> str:
    """Format a complete source string while preserving its newline convention."""
    return format_text_with_diagnostics(text, config=config, strict=strict).text


def check_format(
    text: str,
    *,
    config: FormatterConfig = DEFAULT_CONFIG,
) -> list[tuple[int, str]]:
    """Return ``(line_number, reason)`` entries for changes and diagnostics."""
    result = format_text_with_diagnostics(text, config=config)
    issues: list[tuple[int, str]] = [
        (line, "needs reformatting") for line in result.changed_lines
    ]
    issues.extend((item.line, item.message) for item in result.diagnostics)
    return sorted(issues, key=lambda item: item[0])


def _read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _atomic_write(path: str, text: str, backup_suffix: str | None) -> None:
    target = Path(path)
    if backup_suffix:
        shutil.copy2(target, str(target) + backup_suffix)

    stat_result = target.stat()
    fd, temporary_name = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.chmod(temporary_name, stat_result.st_mode)
        os.replace(temporary_name, target)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report files requiring changes")
    mode.add_argument("--diff", action="store_true", help="print unified diffs")
    mode.add_argument("--in-place", action="store_true", help="replace files atomically")
    parser.add_argument("--backup-suffix", metavar="SUFFIX", help="backup suffix used with --in-place")
    parser.add_argument("--strict", action="store_true", help="refuse output when any ambiguity is reported")
    parser.add_argument("--verbose", action="store_true", help="print all diagnostics")
    parser.add_argument("--indent-size", type=int, default=DEFAULT_CONFIG.indent_size)
    parser.add_argument("--comment-indent", type=int, default=DEFAULT_CONFIG.comment_indent)
    parser.add_argument("--min-comment-gap", type=int, default=DEFAULT_CONFIG.min_comment_gap)
    parser.add_argument("--tab-width", type=int, default=DEFAULT_CONFIG.tab_width)
    parser.add_argument("files", nargs="*", default=["-"], help="assembly files, or - for stdin")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.backup_suffix and not args.in_place:
        print("fmt6502: --backup-suffix requires --in-place", file=sys.stderr)
        return 2
    if args.in_place and "-" in args.files:
        print("fmt6502: --in-place cannot be used with stdin", file=sys.stderr)
        return 2

    try:
        config = FormatterConfig(
            indent_size=args.indent_size,
            comment_indent=args.comment_indent,
            min_comment_gap=args.min_comment_gap,
            tab_width=args.tab_width,
        )
        sources = {path: _read_text(path) for path in args.files}
        results = format_sources(sources, config=config, strict=False)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"fmt6502: {exc}", file=sys.stderr)
        return 2

    diagnostics = [
        diagnostic
        for result in results.values()
        for diagnostic in result.diagnostics
    ]
    if args.verbose or args.strict or any(item.severity == "error" for item in diagnostics):
        for diagnostic in diagnostics:
            print(diagnostic.render(), file=sys.stderr)

    if args.strict and diagnostics:
        return 2

    changed = False
    for path in args.files:
        source = sources[path]
        result = results[path]
        if result.text != source:
            changed = True

        if args.check:
            if result.text != source:
                print(path)
            continue

        if args.diff:
            diff = difflib.unified_diff(
                source.splitlines(keepends=True),
                result.text.splitlines(keepends=True),
                fromfile=path,
                tofile=path,
            )
            sys.stdout.writelines(diff)
            continue

        if args.in_place:
            if result.text != source:
                _atomic_write(path, result.text, args.backup_suffix)
            continue

        sys.stdout.write(result.text)

    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())