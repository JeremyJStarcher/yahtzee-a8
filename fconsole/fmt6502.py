#!/usr/bin/env python3
"""
Syntax-aware source formatter for ca65/cc65 assembly language.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterator


class State(Enum):
    NORMAL = "normal"
    DOUBLE_QUOTE = 'double_quote'
    SINGLE_QUOTE = 'single_quote'
    ESCAPE = 'escape'
    COMMENT = 'comment'


@dataclass(frozen=True)
class Token:
    kind: str          # 'label' | 'opcode' | 'operand' | 'comment' | 'other'
    text: str
    pos: int           # character offset within original line


def _scan_line(line: str) -> list[Token]:
    """
    Character-by-character lexer producing labeled tokens from an assembly line.

    Returns list of Token objects preserving original positions.
    """
    tokens: list[Token] = []
    i = 0
    state = State.NORMAL
    buf = ""
    start_pos = 0

    def flush(kind: str) -> None:
        nonlocal buf, start_pos
        if buf:
            tokens.append(Token(kind=kind, text=buf, pos=start_pos))
            buf = ""
            start_pos = 0

    while i < len(line):
        ch = line[i]
        cp = ord(ch)

        if state is State.COMMENT:
            # accumulate until end-of-line; whole thing becomes one token
            buf += ch
            i += 1
            continue

        if state is State.DOUBLE_QUOTE:
            if ch == '"':
                buf += ch
                i += 1
                state = State.NORMAL
            elif ch == "\\":
                buf += ch
                i += 1
                if i < len(line):
                    buf += line[i]
                    i += 1
                # stays in escape? spec says escaped char inside quote
                # we just keep going, treating backslash+next as literal pair
            else:
                buf += ch
                i += 1
            continue

        if state is State.SINGLE_QUOTE:
            if ch == "'" and (i + 1 >= len(line) or line[i + 1] != "'"):
                buf += ch
                i += 1
                state = State.NORMAL
            elif ch == "'" and i + 1 < len(line) and line[i + 1] == "'":
                # doubled single-quote '' -> literal '
                buf += ch
                buf += line[i + 1]
                i += 2
            elif ch == "\\":
                buf += ch
                i += 1
                if i < len(line):
                    buf += line[i]
                    i += 1
            else:
                buf += ch
                i += 1
            continue

        if state is State.ESCAPE:
            # Should not happen given transitions above; treat as normal char
            buf += ch
            state = State.NORMAL
            i += 1
            continue

        # ----- NORMAL state -----
        if cp in (0x20, 0x09):          # space / tab: separator between tokens
            flush("other")
            start_pos = i + 1
            i += 1
            continue

        if ch == ';':
            # anything before this becomes one token, rest is comment
            if buf:
                tokens.append(Token(kind="other", text=buf, pos=start_pos))
                buf = ""
            # collect trailing chars including the semicolon itself
            while i < len(line):
                buf += line[i]
                i += 1
            tokens.append(Token(kind="comment", text=buf, pos=i - len(buf)))
            return tokens

        if ch == '"':
            flush("other")
            buf = ch
            start_pos = i
            i += 1
            state = State.DOUBLE_QUOTE
            continue

        if ch == "'":
            flush("other")
            buf = ch
            start_pos = i
            i += 1
            state = State.SINGLE_QUOTE
            continue

        if ch == ':':
            buf += ch
            # A colon immediately after a non-empty token is part of label
            if not buf or buf != ":":
                pass
            else:
                # standalone colon -> treat as other (rare)
                flush("other")
                start_pos = i + 1
                i += 1
                continue
            i += 1
            # keep accumulating in buf until we hit whitespace/comment/etc.
            continue

        if ch == '=' and not buf:
            # Symbol assignment: keep the equals attached to whatever precedes or follows.
            # We treat it like any other non-whitespace character so the whole line becomes
            # one contiguous "other" token (or two, if spaces surround it).
            pass  # fall through to ordinary-character handling below

        # ordinary character
        if not buf:
            start_pos = i
        buf += ch
        i += 1

    # end while

    if state is State.COMMENT and buf:
        tokens.append(Token(kind="comment", text=buf, pos=start_pos))
    elif buf:
        tokens.append(Token(kind="other", text=buf, pos=start_pos))

    return tokens


def _find_operation(tokens: list[Token]) -> tuple[int | None, Token | None]:
    """
    Return the index of the operation field token within *tokens*.

    Rules (per PLAN §5):
      - Global/local labels are skipped.
      - Symbol assignments ('SYM = value') have no operation.
      - Pseudo-ops, macro calls, or actual opcodes that follow a label become operation.
    """
    if len(tokens) >= 3 and tokens[1].kind == "other" and tokens[1].text.strip() == "=":
        return None, None

    for idx, tok in enumerate(tokens):
        txt = tok.text
        if tok.kind != "other":
            continue
        stripped = txt.strip()
        if not stripped:
            continue
        # Skip initial label(s)
        if stripped.endswith(":"):
            continue
        # First non-label other-token is the operation
        return idx, tok

    return None, None


# 56 official NMOS 6502 mnemonics (case-insensitive comparison; always emit uppercase)
_NMOS_OPCODES = frozenset({
    "ADC", "AND", "ASL", "BCC", "BCS", "BEQ", "BIT", "BMI",
    "BNE", "BPL", "BRK", "BVC", "BVS", "CLC", "CLD", "CLI",
    "CLV", "CMP", "CPX", "CPY", "DEC", "DEX", "DEY", "EOR",
    "INC", "INX", "INY", "JMP", "JSR", "LDA", "LDX", "LDY",
    "LSR", "NOP", "ORA", "PHA", "PHP", "PLA", "PLP", "ROL",
    "ROR", "RTI", "RTS", "SBC", "SEC", "SED", "SEI", "STA",
    "STX", "STY", "TAX", "TAY", "TSX", "TXA", "TXS", "TYA",
})

_PSEUDO_OPS = {
    ".byte", ".word", ".dbyt", ".addr", ".asciiz", ".null",
    ".proc", ".endproc", ".segment", ".data", ".code", ".bss",
    ".rodata", ".zeropage", ".export", ".global", ".import",
    ".include", ".incbin", ".if", ".else", ".endif", ".macro",
    ".endmacro", ".repeat", ".endrepeat", ".scope", ".res",
    ".ds", ".dz", ".align", ".pad", ".assert", ".warning",
    ".error", ".reloc", ".far", ".near", ".cond", ".endcond",
}


def _classify_operation(token: Token) -> str:
    """
    Return 'UPPER' for recognized 6502 opcodes, 'lower' for pseudo-ops,
    or 'preserve' otherwise.
    """
    text = token.text.strip()
    upper_text = text.upper()

    if upper_text in _NMOS_OPCODES:
        return "UPPER"

    lower_text = text.lower()
    # Allow common prefixes that are definitely pseudo-ops
    if lower_text.startswith("."):
        return "LOWER"
    # Known macro-style names from existing corpus (LOAD16, PUSHALL etc)
    # We treat anything not an opcode and not starting with . as LOWER per spec §6.4
    # because it is a macro call / alias. If user wants stricter behavior they can extend.
    return "LOWER"


def format_line(line: str) -> tuple[str, bool]:
    """
    Format a single line.

    Returns (formatted_line, was_changed).
    Raises ValueError on malformed input (unterminated quote, ambiguous parse).
    """
    original = line.rstrip("\n\r")
    stripped_check = original.lstrip(" \t")
    
    if not stripped_check:
        # blank or whitespace-only line: normalize trailing whitespace only
        normalized = original.rstrip(" \t")
        changed = normalized != original
        return normalized, changed

    tokens = _scan_line(original)

    # Basic quote-balance check on whole line (not per-token, since a token may contain only one of a pair).
    if original.count('"') % 2 != 0 or original.count("'") % 2 != 0:
        raise ValueError(f"Unterminated quoted string in: {original!r}")

    _, op_token = _find_operation(tokens)
    casing = _classify_operation(op_token) if op_token else None

    def transform(token: Token) -> str:
        txt = token.text
        if token.kind == "comment":
            return txt
        if token.kind == "other" and token is op_token and casing == "UPPER":
            return txt.upper()
        if token.kind == "other" and token is op_token and casing == "LOWER":
            return txt.lower()
        return txt

    transformed_tokens: list[tuple[str, bool]] = []
    for tok in tokens:
        transformed_tokens.append((transform(tok), tok.kind == "comment"))

    # Separate code tokens and comment token(s).
    code_parts: list[str] = []
    comment_parts: list[str] = []
    for text, is_comment in transformed_tokens:
        if is_comment:
            comment_parts.append(text)
        else:
            code_parts.append(text)

    # Join code parts with exactly one space between each pair.
    # Each part may be a single character or multi-char run; we just ensure spacing.
    code_str = ""
    for idx, part in enumerate(code_parts):
        if idx > 0:
            prev = code_parts[idx - 1]
            cur = part
            # If previous already ends with space or current starts with space,
            # avoid double-space. Otherwise insert one space.
            if not (prev.endswith(" ") or cur.startswith(" ")):
                code_str += " "
        code_str += part

    import re as _re
    # Collapse any runs of spaces/tabs within code region to single spaces.
    code_str = _re.sub(r"[ \t]+", " ", code_str).strip()

    # Fix commas: no whitespace before comma, exactly one after (unless followed by ;)
    code_str = _re.sub(r"\s+,", ",", code_str)
    def _comma_space(m: _re.Match) -> str:
        follower = m.group(1)
        return ", " + follower if not follower.startswith(";") else ","
    code_str = _re.sub(r",(\S)", _comma_space, code_str)

    # Build final line: preserve comment text EXACTLY including leading semicolons.
    # Join all comment parts verbatim.
    comment_str = "".join(comment_parts) if comment_parts else ""

    INDENT_SIZE = 4
    COMMENT_INDENT = 40
    MIN_COMMENT_GAP = 2
    
    if comment_str:
        # Determine where the first ';' occurs in comment_str.
        semi_pos_in_comment = comment_str.find(';')
        visible_code_len = len(code_str.rstrip())
        
        if visible_code_len < COMMENT_INDENT:
            # Pad code so that semicolon starts at COMMENT_INDENT
            pad = " " * (COMMENT_INDENT - visible_code_len)
            formatted_line = f"{code_str}{pad}{comment_str}"
        else:
            # Code already long enough; keep it left-justified and add gap.
            gap = " " * MIN_COMMENT_GAP
            formatted_line = f"{code_str.rstrip()}{gap}{comment_str}"
    else:
        formatted_line = code_str

    # Preserve original left-margin vs indented status for non-blank lines.
    leading_ws_len = len(original) - len(stripped_check)
    if leading_ws_len == 0:
        formatted_line = formatted_line.lstrip(" \t")
    else:
        formatted_line = (" " * INDENT_SIZE) + formatted_line.lstrip(" \t")

    changed = formatted_line != original
    return formatted_line, changed


def format_text(text: str) -> str:
    """Format entire text preserving newlines."""
    out_lines: list[str] = []
    for raw in text.splitlines(keepends=True):
        formatted, _ = format_line(raw)
        out_lines.append(formatted + ("\n" if raw.endswith("\n") else ""))
    return "".join(out_lines)


def check_format(text: str) -> list[tuple[int, str]]:
    """
    Return list of (line_number, reason) for lines needing formatting or errors.
    Line numbers are 1-based.
    """
    issues: list[tuple[int, str]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        try:
            expected, changed = format_line(raw)
            if changed:
                issues.append((lineno, "needs reformatting"))
        except ValueError as exc:
            issues.append((lineno, str(exc)))
    return issues


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:] or ["-"]:
        data = sys.stdin.read() if path == "-" else open(path).read()
        print(format_text(data), end="")