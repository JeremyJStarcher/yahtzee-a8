# Project Specification: `format-m65.py`

## 1. Overview

A Python script, using the standard library only, to reformat 6502 assembly source code.

- **Input:** A source file, for example `source.asm`.
- **Output:** A new file with the same name plus a `~` suffix, for example `source.asm~`.
- If the `~` file already exists, it is overwritten.
- The script **must not** use regular expressions for parsing strings. A token-based lexer that respects string literals is required.

---

## 2. General Rules

| Rule | Description |
|---|---|
| **Case** | All labels and 6502 opcodes are converted to **upper case**. Directives and pseudo-ops, for example `.proc`, are also converted to uppercase, for example `.PROC`. |
| **Indentation** | Opcodes, origin directives `*=`, and any instruction-like lines are indented by a configurable number of spaces. The default is `4`. |
| **Comments** | Inline comments are allowed, separated by at least one space from the code. Standalone comment lines are preserved with their original indentation. Only trailing whitespace is trimmed. |
| **Blank lines** | One blank line is kept as is. Two blank lines are kept as is. Three or more consecutive blank lines are collapsed to exactly two blank lines. |
| **Trailing whitespace** | Always trim trailing spaces and tabs from every line. |
| **Binary notation** | Preserve binary literals exactly, for example `%00010000`. |
| **High/low byte marks** | Keep angle-bracket notation, for example `#<LABEL` and `#>LABEL`. |
| **String and character constants** | Preserve exactly as written, for example `"HELLO"` and `'A'`. Do not alter their content or case. |
| **Macro parameters** | Placeholders such as `\1` are left untouched. |
| **Line continuations** | Not supported. 6502 assembly does not use `\` continuations. |

---

## 3. Configuration Class

The script shall define a configuration object, or equivalent constants, near the top of the file.

```python
class Config:
    indent_opcodes = 4          # spaces for opcode/indented lines
    add_colon_to_labels = False # if True, append ':' to all labels if not already present
    space_after_comma = True    # add a space after commas in operands
    comment_column = 15         # preferred minimum column for inline comments
```

---

## 4. Line Structure: Internal Representation

Each line is parsed into the following fields.

| Field | Type | Description |
|---|---|---|
| `label` | `str \| None` | A label without a colon. If `add_colon_to_labels` is `True`, a colon will be added when formatting. |
| `directive` | `str \| None` | A dot-directive, for example `.PROC`, `.MACRO`, or `.INCLUDE`. Maximum one per line. |
| `pseudo_op` | `str \| None` | A pseudo-opcode starting with a dot, for example `.BYTE`, `.WORD`, `.DS`, `.EQU`, or `.SET`. Maximum one per line. |
| `opcode` | `str \| None` | A 6502 instruction from the whitelist in the appendix. |
| `operators` | `list[str]` | Tokenized operands. For opcodes, examples include `["LABEL", "+", "5"]`. For directives and pseudo-ops, this contains argument tokens. |
| `index_reg` | `str \| None` | The index register for indexed addressing, for example `Y` in `LDA 495,Y`. |
| `comment` | `str \| None` | Comment text without the leading semicolon. |
| `is_origin` | `bool` | `True` if the line is an origin directive, for example `*=$00CB`. |

---

## 5. Parsing Approach: No Regex for Strings

Use a character-by-character lexer that respects quoted regions.

The lexer must handle:

- Double-quoted strings, for example `"..."`.
- Single-quoted character constants, for example `'A'`.
- Labels, meaning words not in the opcode list.
- Opcodes.
- Dot-directives.
- Numbers, including hex `$`, binary `%`, and decimal.
- Operators: `+`, `-`, `*`, `/`, `<`, and `>`.
- Commas.
- Semicolons as comment markers.
- The origin token `*=`.

Comments start with `;` and run to the end of the line. They are stored separately from the code tokens.

---

## 6. Formatting Rules by Component

### 6.1 Labels

- Labels must be flush left, with no leading whitespace.
- A label is any word that is not a 6502 opcode, case-insensitively.
- Labels are converted to **upper case**.
- If `add_colon_to_labels` is `True`, a colon is appended if not already present.
- Local labels, for example `LABEL?` or `?LABEL`, are treated the same as ordinary labels.

### 6.2 Directives and Pseudo-Opcodes

Examples include `.PROC`, `.MACRO`, `.BYTE`, `.WORD`, `.DS`, `.EQU`, `.SET`, and `.INCLUDE`.

- Directives and pseudo-opcodes must be flush left.
- They are converted to **upper case**, for example `.proc` becomes `.PROC`.
- Operands are formatted with spaces after commas if `space_after_comma` is `True`.
- Operators are surrounded with spaces.

### 6.3 Origin Directives

Origin directives, for example `*=$00CB`, are indented like opcodes using `indent_opcodes` spaces.

The `*=` token is treated as the instruction part. The operand follows the same spacing rules as other operands.

### 6.4 6502 Opcodes

- Opcodes must be from the whitelist in the appendix.
- Opcodes are converted to **upper case**.
- Opcodes are indented by `indent_opcodes` spaces.

Operand formatting rules:

- Place one space after the opcode.
- Add spaces around arithmetic operators, for example `LABEL + 5` and `#HIGHEST + 1`.
- Add one space after each comma if `space_after_comma` is `True`, for example `$92, X`.
- The index register, if any, is placed after the comma using the same comma-spacing rule.
- Immediate values keep the `#` prefix.
- Hex values keep the `$` prefix.
- Binary values keep the `%` prefix, or are preserved exactly if written as plain digits.

### 6.5 Comments

#### Inline comments

- Reassemble inline comments with a space before the semicolon.
- If the comment can be placed at or after `comment_column`, pad with spaces to that column.
- Otherwise, place it at the end of the line with a single preceding space.

#### Standalone comment lines

- Preserve original indentation.
- Keep leading spaces and tabs.
- Trim trailing whitespace.
- Trim leading and trailing spaces from the comment text after the semicolon.

### 6.6 Operators

For opcode operands, expressions are tokenized using C-style parsing rules.

When reformatting, insert a space before and after these operators:

```text
+ - * /
```

When reformatting, do NOT insert a space before and after these operators:


```text
< >
```


For directives, apply the same spacing where operators appear.

### 6.7 Blank Lines

Blank lines follow the general rules:

- One blank line is kept as is.
- Two consecutive blank lines are kept as is.
- Three or more consecutive blank lines are collapsed to exactly two blank lines.

---

## 7. Summary of Clarifications from Review

| Issue | Decision |
|---|---|
| Origin directive indentation | Indent like opcodes, using 4 spaces by default. |
| Labels and colons | No colon is required. A config flag, `add_colon_to_labels`, controls whether to add one. |
| Local labels | Allowed, for example `LABEL?` or `?LABEL`; treated as normal labels. |
| Standalone comments | Preserve original indentation; only trim trailing whitespace. |
| String literals | Preserve exactly. Do not alter content or case. |
| Character constants | Preserve exactly, for example `'A'`. |
| Spaces around operators | Yes, for `+`, `-`, `*`, `/`, `<`, and `>`. |
| Pseudo-ops beyond `.BYTE` | All are handled, including `.EQU`, `.SET`, `.RES`, `.END`, and others, with the same rules. |
| Macro parameters | Leave parameters such as `\1` unchanged. |
| Case of directives | Convert directives to uppercase, for example `.proc` becomes `.PROC`. |
| Line continuations | Not supported. |
| Comment trimming | Trim leading and trailing spaces in comment text. |
| Empty lines with spaces | Treat as blank lines and collapse according to the blank-line rules. |
| Indentation for non-opcode lines | Labels are flush left. Comments on the same line follow inline comment rules. |

---

## 8. Appendix: 6502 Opcode Whitelist

The following mnemonics must be recognized case-insensitively. Any word not in this list is treated as a label.

```text
ADC, AND, ASL, BCC, BCS, BEQ, BIT, BMI, BNE, BPL, BRK, BVC, BVS,
CLC, CLD, CLI, CLV, CMP, CPX, CPY, DEC, DEX, DEY, EOR, INC, INX,
INY, JMP, JSR, LDA, LDX, LDY, LSR, NOP, ORA, PHA, PHP, PLA, PLP,
ROL, ROR, RTI, RTS, SBC, SEC, SED, SEI, STA, STX, STY, TAX, TAY,
TSX, TXA, TXS, TYA
```

---

## 9. Implementation Notes

- The lexer must not rely on regular expressions for tokenizing strings.
- Use a state machine that handles quoted regions.
- When reassembling, use the internal line structure to produce the final string.
- Apply all formatting rules consistently.
- The script should be callable from the command line.

Example:

```bash
python format-m65.py source.asm
```

Error handling:

- If a line cannot be parsed, leave it unchanged, or log a warning, and continue.

---

## End of Specification
