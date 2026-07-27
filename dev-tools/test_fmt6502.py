#!/usr/bin/env python3
"""Regression tests for fmt6502."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

from fmt6502 import (
    FormatError,
    FormatterConfig,
    check_format,
    format_line,
    format_sources,
    format_text,
    format_text_with_diagnostics,
)


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(title)
    print("=" * 60)


def test_case(name: str, func: Callable[[], bool]) -> bool:
    try:
        ok = func()
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"{status}: {name}")
        return ok
    except Exception as exc:
        print(f"✗ EXCEPTION in {name}: {exc}")
        return False


def test_blank_line() -> bool:
    line, changed = format_line("   \n")
    assert line == "", f"expected empty, got {line!r}"
    assert changed
    return True


def test_standalone_comment() -> bool:
    line, _ = format_line("; just a comment\n")
    assert line == "; just a comment"
    return True


def test_standalone_comment_inherits_indented_code() -> bool:
    source = "        LDA #$00\n; inherited\n"
    out = format_text(source)
    assert out.splitlines()[1] == "    ; inherited", repr(out)
    return True


def test_standalone_comment_inherits_margin_code() -> bool:
    source = "@loop:\n        ; inherited\n"
    out = format_text(source)
    assert out.splitlines()[1] == "; inherited", repr(out)
    return True


def test_comment_inheritance_crosses_blank_line() -> bool:
    source = "        LDA #$00\n\n; inherited\n"
    out = format_text(source)
    assert out.splitlines()[2] == "    ; inherited", repr(out)
    return True


def test_indented_code_preserves_margin() -> bool:
    out, _ = format_line("\t\tLDA #$00\n")
    assert out == "    LDA #$00", repr(out)
    return True


def test_left_margin_stays_zero() -> bool:
    out, _ = format_line("lda #$00\n")
    assert out == "LDA #$00", repr(out)
    return True


def test_label_only() -> bool:
    out, _ = format_line("@loop:\n")
    assert out == "@loop:"
    return True


def test_label_plus_opcode() -> bool:
    out, _ = format_line("@loop: inx\n")
    assert out == "@loop: INX", repr(out)
    return True


def test_global_label() -> bool:
    out, _ = format_line("_reset_handler:\n")
    assert out == "_reset_handler:"
    return True


def test_symbol_assignment_spaced() -> bool:
    out, _ = format_line("SCREEN_COLS = 40\n")
    assert out == "SCREEN_COLS = 40", repr(out)
    return True


def test_symbol_assignment_unspaced() -> bool:
    out, _ = format_line("SCREEN_COLS=40\n")
    assert out == "SCREEN_COLS=40", repr(out)
    return True


def test_comma_spacing_simple() -> bool:
    out, _ = format_line("STA $C000 ,\tX\n")
    assert out == "STA $C000, X", repr(out)
    return True


def test_comma_at_end_has_no_space() -> bool:
    out, _ = format_line(".byte $01,\n")
    assert out == ".byte $01,", repr(out)
    return True


def test_inline_comment_exact_column() -> bool:
    out, _ = format_line("        LDA #$00 ; load zero\n")
    assert out.index(";") == 40, repr(out)
    return True


def test_inline_comment_past_column() -> bool:
    code = "    LDX #PAGES_TO_COPY + REM_BYTES_TO_COPY + BOTTOM_ROW_OFFSET"
    out, _ = format_line(code + " ; helper\n")
    prefix = out[:out.index(";")]
    assert len(prefix) - len(prefix.rstrip()) == 2, repr(out)
    return True


def test_nmos_opcode_uppercase() -> bool:
    for op in ("lda", "sta", "jmp", "bne", "pHp"):
        out, _ = format_line(f"{op} #$00")
        assert out.startswith(op.upper()), repr(out)
    return True


def test_pseudo_op_lowercase() -> bool:
    for raw in (".BYTE $00", ".WORD $1234", ".RES 1", '.INCLUDE "x.inc"'):
        out, _ = format_line(raw)
        assert out.split()[0].islower(), repr(out)
    return True


def test_macro_definition_and_calls_are_synchronized() -> bool:
    source = ".MACRO PUSH_PTR P\n    PUSH_PTR P\n.ENDMacro\nPUSH_PTR VALUE\n"
    out = format_text(source)
    expected = ".macro push_ptr P\n    push_ptr P\n.endmacro\npush_ptr VALUE\n"
    assert out == expected, f"\nexpected={expected!r}\nactual={out!r}"
    return True


def test_cross_file_macro_synchronization() -> bool:
    results = format_sources({
        "defs.inc": ".MACRO LOAD16 P\n.ENDMACRO\n",
        "main.asm": "        LOAD16 PTR\n",
    })
    assert results["defs.inc"].text == ".macro load16 P\n.endmacro\n"
    assert results["main.asm"].text == "    load16 PTR\n"
    return True


def test_unresolved_macro_is_preserved_and_reported() -> bool:
    result = format_text_with_diagnostics("        EXTERNAL_MACRO PTR\n")
    assert "EXTERNAL_MACRO" in result.text
    assert any("unresolved macro" in d.message for d in result.diagnostics)
    return True


def test_case_collision_is_preserved_and_reported() -> bool:
    source = ".macro COPYBYTE\n.endmacro\n.macro copybyte\n.endmacro\nCOPYBYTE\n"
    result = format_text_with_diagnostics(source)
    assert ".macro COPYBYTE" in result.text
    assert ".macro copybyte" in result.text
    assert result.text.endswith("COPYBYTE\n")
    assert any("collision" in d.message for d in result.diagnostics)
    return True


def test_strict_mode_rejects_ambiguity() -> bool:
    try:
        format_text("EXTERNAL_MACRO\n", strict=True)
    except FormatError:
        return True
    raise AssertionError("strict mode did not reject an unresolved operation")


def test_double_quoted_string_preserved() -> bool:
    original = '        .byte "a,b", "a  b", "semi;colon"\n'
    out = format_text(original)
    assert '"a,b"' in out
    assert '"a  b"' in out
    assert '"semi;colon"' in out
    return True


def test_single_quoted_char_preserved() -> bool:
    original = "        LDA #' '\n"
    out = format_text(original)
    assert "#' '" in out, repr(out)
    return True


def test_apostrophe_in_comment_is_not_a_quote() -> bool:
    original = "; Isn't this version *SO* much better?\n"
    result = format_text_with_diagnostics(original)
    assert result.text == original
    assert not result.diagnostics
    return True


def test_comment_text_exact() -> bool:
    original_comment = ";; double  spaces, commas, and 'quotes' preserved  "
    source = "    LDA #$00     " + original_comment + "\n"
    out = format_text(source)
    assert out[out.index(";"):].rstrip("\n") == original_comment
    return True


def test_unterminated_quote_is_reported_and_line_unchanged() -> bool:
    source = '    .byte "broken\nLDA #0\n'
    result = format_text_with_diagnostics(source)
    assert result.text.splitlines()[0] == '    .byte "broken'
    assert sum("unterminated" in d.message for d in result.diagnostics) == 1
    return True


def test_label_plus_pseudo_op() -> bool:
    out, _ = format_line("CURSX: .RES 1")
    assert out == "CURSX: .res 1", repr(out)
    return True


def test_indexed_addressing() -> bool:
    out, _ = format_line("LDA (PRINT_PTR),Y")
    assert out == "LDA (PRINT_PTR), Y", repr(out)
    return True


def test_global_scope_operand_is_not_a_label() -> bool:
    source = ".REPEAT ::SCREEN_ROWS,I\n"
    result = format_text_with_diagnostics(source)
    assert result.text == ".repeat ::SCREEN_ROWS, I\n", repr(result.text)
    assert not result.diagnostics, [item.render() for item in result.diagnostics]
    return True


def test_scoped_label_still_parses() -> bool:
    out, _ = format_line("outer::inner: lda #0")
    assert out == "outer::inner: LDA #0", repr(out)
    return True


def _write_fake_builder(path: Path, *, formatting_sensitive: bool) -> None:
    if formatting_sensitive:
        lines = [
            "from pathlib import Path",
            "source = Path('main.asm').read_bytes()",
            "Path('build').mkdir(exist_ok=True)",
            "Path('build/bios.bin').write_bytes(source)",
        ]
    else:
        lines = [
            "from pathlib import Path",
            "source = Path('main.asm').read_text(encoding='utf-8')",
            "ops = []",
            "for line in source.splitlines():",
            "    code = line.split(';', 1)[0].strip()",
            "    if not code:",
            "        continue",
            "    token = code.split(None, 1)[0].rstrip(':').upper()",
            "    if token in {'LDA', 'RTS'}:",
            "        ops.append(token)",
            "image = bytearray([0xEA] * 0x1000)",
            "if ops == ['LDA', 'RTS']:",
            "    image[:3] = bytes([0xA9, 0x00, 0x60])",
            "for offset, target in ((0xFFA, 0xF010), (0xFFC, 0xF000), (0xFFE, 0xF020)):",
            "    image[offset] = target & 0xFF",
            "    image[offset + 1] = target >> 8",
            "Path('build').mkdir(exist_ok=True)",
            "Path('build/bios.bin').write_bytes(image)",
            "map_text = (",
            "    'Exports list by name:\\n'",
            "    '---------------------\\n'",
            "    '_irq_handler              00F020 RLA    _nmi_handler              00F010 RLA\\n'",
            "    '_reset_handler            00F000 RLA\\n\\n'",
            ")",
            "Path('build/bios.map').write_text(map_text, encoding='utf-8')",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_build_equivalence_harness_matches() -> bool:
    verifier = Path(__file__).with_name("verify_build_equivalence.py")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp, "project")
        root.mkdir()
        Path(root, "main.asm").write_text("    lda #0\n    rts\n", encoding="utf-8")
        _write_fake_builder(Path(root, "build.py"), formatting_sensitive=False)
        command = f"{shlex.quote(sys.executable)} build.py"
        completed = subprocess.run(
            [
                sys.executable,
                str(verifier),
                str(root),
                "--build-command",
                command,
                "--artifact",
                "build/bios.bin",
                "--map-file",
                "build/bios.map",
                "--export",
                "_reset_handler",
                "--export",
                "_nmi_handler",
                "--export",
                "_irq_handler",
                "--rom-base",
                "0xF000",
                "--vector",
                "NMI=0xFFFA",
                "--vector",
                "RESET=0xFFFC",
                "--vector",
                "IRQ=0xFFFE",
                "--strict-format",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "MATCH: build/bios.bin" in completed.stdout
        assert "MATCH: exports in build/bios.map" in completed.stdout
        assert "MATCH: RESET @ $FFFC -> original $F000, formatted $F000" in completed.stdout
    return True


def test_build_equivalence_harness_detects_mismatch() -> bool:
    verifier = Path(__file__).with_name("verify_build_equivalence.py")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp, "project")
        root.mkdir()
        Path(root, "main.asm").write_text("    lda #0\n", encoding="utf-8")
        _write_fake_builder(Path(root, "build.py"), formatting_sensitive=True)
        command = f"{shlex.quote(sys.executable)} build.py"
        completed = subprocess.run(
            [
                sys.executable,
                str(verifier),
                str(root),
                "--build-command",
                command,
                "--artifact",
                "build/bios.bin",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 1, completed.stdout + completed.stderr
        assert "MISMATCH: build/bios.bin" in completed.stdout
        assert "first differing offset" in completed.stdout
    return True


def test_newline_conventions_preserved() -> bool:
    source = "lda #0\r\nsta $00\r\n"
    out = format_text(source)
    assert out == "LDA #0\r\nSTA $00\r\n", repr(out)
    source = "lda #0\rsta $00\r"
    out = format_text(source)
    assert out == "LDA #0\rSTA $00\r", repr(out)
    return True


def test_final_newline_state_preserved() -> bool:
    assert not format_text("lda #0").endswith(("\n", "\r"))
    assert format_text("lda #0\n").endswith("\n")
    return True


def test_idempotence() -> bool:
    source = (
        ".MACRO PUSHALL\n"
        "    php ; status\n"
        ".ENDMACRO\n"
        "@loop: PUSHALL\n"
        '    .byte "a,b",$02,$03 ; data\n'
    )
    once = format_text(source)
    twice = format_text(once)
    assert once == twice, f"once={once!r}\ntwice={twice!r}"
    return True


def test_check_format_reports_changes() -> bool:
    issues = check_format("lda #$00\nSTA $C000,X\n")
    changed = {line for line, reason in issues if reason == "needs reformatting"}
    assert changed == {1, 2}, issues
    return True


def test_cli_check_and_diff() -> bool:
    script = Path(__file__).with_name("fmt6502.py")
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp, "sample.asm")
        source.write_bytes(b"lda #0\r\n")
        checked = subprocess.run(
            [sys.executable, str(script), "--check", str(source)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert checked.returncode == 1
        assert str(source) in checked.stdout
        diffed = subprocess.run(
            [sys.executable, str(script), "--diff", str(source)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert diffed.returncode == 0
        assert "-lda #0" in diffed.stdout
        assert "+LDA #0" in diffed.stdout
    return True


def test_full_bios_source_no_error() -> bool:
    candidates = [
        Path("bios/src/bios.asm"),
        Path("src/bios.asm"),
    ]
    env_path = os.environ.get("FMT6502_BIOS")
    if env_path:
        candidates.insert(0, Path(env_path))

    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        print("  SKIP: set FMT6502_BIOS or run from the BIOS project root")
        return True

    with open(path, "r", encoding="utf-8", newline="") as handle:
        source = handle.read()
    result = format_text_with_diagnostics(source, filename=str(path))
    errors = [d for d in result.diagnostics if d.severity == "error"]
    assert not errors, [d.render() for d in errors]
    assert len(source.splitlines()) == len(result.text.splitlines())
    assert format_text(result.text) == result.text
    return True


TESTS = [
    ("Blank line", test_blank_line),
    ("Standalone comment", test_standalone_comment),
    ("Comment inherits indented code", test_standalone_comment_inherits_indented_code),
    ("Comment inherits margin code", test_standalone_comment_inherits_margin_code),
    ("Comment inheritance crosses blank", test_comment_inheritance_crosses_blank_line),
    ("Indented margin normalized", test_indented_code_preserves_margin),
    ("Left-margin zero indent", test_left_margin_stays_zero),
    ("Label-only line", test_label_only),
    ("Label plus opcode", test_label_plus_opcode),
    ("Global label", test_global_label),
    ("Spaced symbol assignment", test_symbol_assignment_spaced),
    ("Unspaced symbol assignment", test_symbol_assignment_unspaced),
    ("Comma spacing", test_comma_spacing_simple),
    ("Terminal comma", test_comma_at_end_has_no_space),
    ("Inline comment exact column", test_inline_comment_exact_column),
    ("Long inline comment gap", test_inline_comment_past_column),
    ("NMOS opcode uppercase", test_nmos_opcode_uppercase),
    ("Pseudo-op lowercase", test_pseudo_op_lowercase),
    ("Macro definition/call synchronization", test_macro_definition_and_calls_are_synchronized),
    ("Cross-file macro synchronization", test_cross_file_macro_synchronization),
    ("Unresolved macro safety", test_unresolved_macro_is_preserved_and_reported),
    ("Case-collision safety", test_case_collision_is_preserved_and_reported),
    ("Strict-mode rejection", test_strict_mode_rejects_ambiguity),
    ("Double-quoted strings preserved", test_double_quoted_string_preserved),
    ("Single-quoted character preserved", test_single_quoted_char_preserved),
    ("Apostrophe in comment", test_apostrophe_in_comment_is_not_a_quote),
    ("Comment text exact", test_comment_text_exact),
    ("Unterminated quote safety", test_unterminated_quote_is_reported_and_line_unchanged),
    ("Label plus pseudo-op", test_label_plus_pseudo_op),
    ("Indexed addressing", test_indexed_addressing),
    ("Global-scope operand", test_global_scope_operand_is_not_a_label),
    ("Scoped label", test_scoped_label_still_parses),
    ("Build equivalence match", test_build_equivalence_harness_matches),
    ("Build equivalence mismatch", test_build_equivalence_harness_detects_mismatch),
    ("Newline conventions", test_newline_conventions_preserved),
    ("Final newline state", test_final_newline_state_preserved),
    ("Idempotence", test_idempotence),
    ("check_format reports changes", test_check_format_reports_changes),
    ("CLI check and diff", test_cli_check_and_diff),
    ("Full bios.asm no error", test_full_bios_source_no_error),
]


def main() -> int:
    print("=" * 60)
    print("fmt6502 - Formatter Test Suite")
    print("=" * 60)

    results = [(name, test_case(name, func)) for name, func in TESTS]

    _section("Summary")
    passed = sum(ok for _, ok in results)
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}: {name}")
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())