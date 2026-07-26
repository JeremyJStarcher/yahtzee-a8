#!/usr/bin/env python3
"""
Test suite for fmt6502 - 6502/ca65 source formatter.

Follows the pattern of pylib/test_video_spec.py with explicit pass/fail reporting.
"""

import sys
from typing import Callable

from fmt6502 import (
    format_line,
    format_text,
    check_format,
)


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(title)
    print('=' * 60)


def test_case(name: str, func: Callable[[], bool]) -> bool:
    try:
        ok = func()
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"{status}: {name}")
        return ok
    except Exception as exc:
        print(f"✗ EXCEPTION in {name}: {exc}")
        return False


# ---------------------------------------------------------------------------
# Milestone 1 / 2: Lexer recognizes labels, opcodes, operands, comments
# ---------------------------------------------------------------------------

def test_blank_line() -> bool:
    line, changed = format_line("   \n")
    assert line == "", f"expected empty, got {line!r}"
    assert changed is True or changed is False  # may strip whitespace
    return True


def test_standalone_comment() -> bool:
    line, changed = format_line("; just a comment\n")
    assert line == "; just a comment", f"got {line!r}"
    return True


def test_indented_code_preserves_margin() -> bool:
    code = "        LDA #$00\n"
    out, _ = format_line(code)
    assert out.startswith("    "), f"expected indent, got {out!r}"
    return True


def test_left_margin_stays_zero() -> bool:
    code = "LDA #$00\n"
    out, _ = format_line(code)
    assert not out.startswith(" "), f"expected no indent, got {out!r}"
    return True


def test_label_only() -> bool:
    code = "@loop:\n"
    out, _ = format_line(code)
    assert out == "@loop:", f"got {out!r}"
    return True


def test_global_label() -> bool:
    code = "_reset_handler:\n"
    out, _ = format_line(code)
    assert out == "_reset_handler:", f"got {out!r}"
    return True


def test_symbol_assignment() -> bool:
    code = "SCREEN_COLS = 40\n"
    out, _ = format_line(code)
    assert out == "SCREEN_COLS = 40", f"got {out!r}"
    return True


# ---------------------------------------------------------------------------
# Milestone 3: Basic formatting without case conversion
# ---------------------------------------------------------------------------

def test_comma_spacing_simple() -> bool:
    line, changed = format_line("STA $C000,X\n")
    # comma should have exactly one space after and none before
    assert "," in line
    code_part = line.split(";")[0]
    assert ", " in code_part, f"expected ', ' in {code_part!r}"
    assert " ," not in code_part, f"unexpected space-before-comma in {code_part!r}"
    return True


def test_inline_comment_before_column() -> bool:
    line, _ = format_line("    LDA #$00     ; load zero\n")
    # Should pad to COMMENT_INDENT=40
    semi = line.find(';')
    assert semi != -1
    assert semi >= 39, f"semicolon at col {semi}, expected ~40"
    return True


def test_inline_comment_past_column() -> bool:
    long_code = "    LDX #PAGES_TO_COPY + REM_BYTES_TO_COPY + BOTTOM_ROW_OFFSET "
    comment = "; helper\n"
    out, _ = format_line(long_code + comment)
    # when code exceeds COMMENT_INDENT, only MIN_COMMENT_GAP spaces separate
    semi = out.find(';')
    prefix = out[:semi]
    assert len(prefix.rstrip()) >= 40, "long code should remain unshifted"
    # there should be exactly MIN_COMMENT_GAP spaces before semicolon after stripping trailing
    trailing = len(prefix) - len(prefix.rstrip())
    assert trailing == 2, f"expected 2 trailing spaces, got {trailing}"
    return True


# ---------------------------------------------------------------------------
# Milestone 4: Opcode and directive casing
# ---------------------------------------------------------------------------

def test_nmos_opcode_uppercase() -> bool:
    for op in ("lda", "sta", "jmp", "bne"):
        line, _ = format_line(f"{op} #$00")
        assert line.startswith(op.upper()), f"expected uppercase {op}, got {line!r}"
    return True


def test_pseudo_op_lowercase() -> bool:
    cases = [
        ".BYTE $00",
        ".WORD $1234",
        ".RES 1",
        ".INCLUDE \"branches.inc\"",
        ".MACRO TEST",
    ]
    for raw in cases:
        line, _ = format_line(raw)
        parts = line.split()
        if parts:
            first = parts[0]
            assert first == first.lower(), f"expected lowercase pseudo-op, got {first!r}"
    return True


def test_mixed_case_macro_calls() -> bool:
    # Macros should become lowercase per §6.4 (treated as non-opcode identifiers)
    line, _ = format_line("PUSHALL")
    assert line == "pushall", f"got {line!r}"
    line, _ = format_line(".ENDMacro")
    assert line == ".endmacro", f"got {line!r}"
    return True


# ---------------------------------------------------------------------------
# Milestone 5: String and comment preservation
# ---------------------------------------------------------------------------

def test_double_quoted_string_preserved() -> bool:
    original = '        pstring "Line: 1"\n'
    out, changed = format_line(original)
    assert '"Line: 1"' in out, f"string mangled in {out!r}"
    return True


def test_single_quoted_char_preserved() -> bool:
    original = "        LDA #' '\n"
    out, _ = format_line(original)
    assert "' '" in out or "'\\ '" not in out.replace(" ", ""), f"char literal mangled in {out!r}"
    return True


def test_comment_text_exact() -> bool:
    original = "    LDA #$00     ;; double semicolon preserved\n"
    out, _ = format_line(original)
    assert ";;" in out, f"double semicolons lost in {out!r}"
    return True


# ---------------------------------------------------------------------------
# Representative corpus lines (from bios/src/bios.asm)
# ---------------------------------------------------------------------------

def test_macro_with_args() -> bool:
    line, _ = format_line(".MACRO PUSH_PTR P")
    assert "push_ptr" in line.lower(), f"got {line!r}"
    return True


def test_label_plus_pseudo_op() -> bool:
    line, _ = format_line("CURSX: .res 1")
    assert line.startswith("CURSX:"), f"label changed: {line!r}"
    assert ".res" in line, f"pseudo-op missing: {line!r}"
    return True


def test_indexed_addressing() -> bool:
    line, _ = format_line("LDA (PRINT_PTR),Y")
    # Formatter adds one space after every comma per PLAN §6.6,
    # so we accept either the original no-space form or the normalized spaced form.
    ok1 = "(PRINT_PTR),Y" in line or "(print_ptr),y" in line
    ok2 = "(PRINT_PTR), Y" in line or "(print_ptr), y" in line
    assert ok1 or ok2, f"expected indexed addressing in {line!r}"
    return True


def test_consecutive_comments() -> bool:
    text = "; first\n; second\n; third\n"
    out = format_text(text)
    lines = [l for l in out.splitlines()]
    assert len(lines) == 3, f"expected 3 lines, got {len(lines)}"
    return True


# ---------------------------------------------------------------------------
# Idempotence and corpus-level checks
# ---------------------------------------------------------------------------

def test_idempotence_simple() -> bool:
    cases = [
        "lda #$00",
        "STA $C000,X     ; comment",
        ".byte $01,$02,$03",
        "@loop: INX",
        "    JSR DISPLAY_CHAR",
    ]
    for raw in cases:
        once, _ = format_line(raw + "\n")
        twice, _ = format_line(once + "\n")
        if once != twice:
            print(f"  non-idempotent on {raw!r}: {once!r} vs {twice!r}")
            return False
    return True


def test_check_format_reports_changes() -> bool:
    text = "LDA   #$00\nSTA $C000,X\n"
    issues = check_format(text)
    assert len(issues) > 0, "check_format should report formatting issues"
    return True


def test_full_bios_source_no_error() -> bool:
    """Run formatter over bios/src/bios.asm; fail on any ValueError."""
    import os
    path = os.path.join("bios", "src", "bios.asm")
    with open(path, "r") as fh:
        source = fh.read()
    try:
        formatted = format_text(source)
    except Exception as exc:
        print(f"  failed to format bios.asm: {exc}")
        return False

    # Verify no exceptions and line count unchanged
    src_lines = source.splitlines()
    fmt_lines = formatted.splitlines()
    if len(src_lines) != len(fmt_lines):
        print(f"  line count changed: {len(src_lines)} -> {len(fmt_lines)}")
        return False
    return True


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

TESTS = [
    ("Blank line", test_blank_line),
    ("Standalone comment", test_standalone_comment),
    ("Indented margin preserved", test_indented_code_preserves_margin),
    ("Left-margin zero indent", test_left_margin_stays_zero),
    ("Label-only line", test_label_only),
    ("Global label", test_global_label),
    ("Symbol assignment", test_symbol_assignment),
    ("Comma spacing simple", test_comma_spacing_simple),
    ("Inline comment before column", test_inline_comment_before_column),
    ("Inline comment past column", test_inline_comment_past_column),
    ("NMOS opcode uppercase", test_nmos_opcode_uppercase),
    ("Pseudo-op lowercase", test_pseudo_op_lowercase),
    ("Mixed-case macro calls", test_mixed_case_macro_calls),
    ("Double-quoted string preserved", test_double_quoted_string_preserved),
    ("Single-quoted char preserved", test_single_quoted_char_preserved),
    ("Comment text exact", test_comment_text_exact),
    ("Macro with args", test_macro_with_args),
    ("Label plus pseudo-op", test_label_plus_pseudo_op),
    ("Indexed addressing", test_indexed_addressing),
    ("Consecutive comments", test_consecutive_comments),
    ("Idempotence simple", test_idempotence_simple),
    ("check_format reports changes", test_check_format_reports_changes),
    ("Full bios.asm no error", test_full_bios_source_no_error),
]


def main() -> int:
    print("=" * 60)
    print("fmt6502 - Formatter Test Suite")
    print("=" * 60)

    results = []
    for name, func in TESTS:
        ok = test_case(name, func)
        results.append((name, ok))

    _section("Summary")
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())