# Plan: 6502/ca65 Source Formatter

## 1. Purpose

Create a syntax-aware source formatter for 6502 assembly written for ca65.

The formatter will change presentation only. It must preserve program meaning, strings, expressions, comments, symbol references, and generated machine code.

The first version should process `.asm` and `.inc` files. Files such as `Makefile`, `README.md`, and linker configuration files should be ignored unless explicitly requested.

## 2. Formatting Configuration

The formatter should expose these settings:

* `INDENT_SIZE`: number of spaces used for every indented code line.
* `COMMENT_INDENT`: preferred column for inline comments.
* `MIN_COMMENT_GAP`: minimum spaces before an inline comment when the code already reaches `COMMENT_INDENT`.
* `CPU`: initially fixed to official NMOS 6502 opcodes.
* `TAB_WIDTH`: used only when interpreting existing indentation.
* `NEWLINE_MODE`: preserve existing line endings by default.

Tabs in assembly indentation should be replaced with spaces.

## 3. Parsing Strategy

Do not implement this as a series of regular-expression replacements.

Each line should be scanned character by character using these lexical states:

1. Normal source text.
2. Double-quoted string.
3. Single-quoted character or string.
4. Escaped character inside a quoted value.
5. Comment.

A semicolon starts a comment only while the scanner is in normal source text. Semicolons inside quoted values must remain part of the value.

Likewise, comma formatting must only affect commas in normal source text. Commas inside strings and comments must not be changed.

## 4. Line Classification

Every line should be classified before formatting:

* Blank line.
* Standalone comment.
* Left-margin code.
* Indented code.
* Label-only line.
* Label followed by an operation.
* Symbol assignment or constant definition.
* Operation-only line.
* Operation with operands.
* Operation with inline comment.

The parser should recognize:

* Global labels such as `_reset_handler:`.
* Local labels such as `@loop:`.
* Label-plus-operation lines such as `CURSX: .res 1`.
* Symbol assignments such as `SCREEN_COLS = 40`.
* Pseudo-ops such as `.proc`, `.segment`, `.macro`, and `.byte`.
* Macro invocations such as `LOAD16`, `PUSHALL`, and `ADD16`.
* Actual 6502 instructions such as `LDA`, `STA`, `JSR`, and `RTS`.

## 5. Definition of “First Word”

Interpret “first word” as the operation field, not necessarily the physically first token on the line.

Examples:

* In `LDA #$00`, the operation is `LDA`.
* In `line_1: pstring "Line: 1"`, the operation is `pstring`.
* In `CURSX: .res 1`, the operation is `.res`.
* In `@loop:`, there is no operation.
* In `SCREEN_COLS = 40`, there is no operation.

Labels, constant names, operands, strings, and comments should not be case-converted merely because they are the first physical token.

## 6. Rule Precedence

Apply rules in this order.

### 6.1 Blank Lines

Preserve blank lines.

Trailing spaces may be removed, but blank lines should not be inserted, removed, or collapsed.

### 6.2 Standalone Comments

A standalone comment inherits the indentation level of the preceding formatted nonblank line:

* Zero spaces when the preceding line is at the left margin.
* `INDENT_SIZE` spaces when the preceding line is indented.

Consecutive standalone comments inherit the same level.

At the beginning of a file, where no preceding line exists, preserve whether the original comment was flush-left or indented.

Using the preceding nonblank line is preferable to using the immediately preceding physical line because blank separator lines have no meaningful indentation.

### 6.3 Code Indentation

For non-comment code:

* If the original line begins in column zero, keep it in column zero.
* If the original line has any leading spaces or tabs, replace them with exactly `INDENT_SIZE` spaces.

Do not independently indent nested `.if`, `.macro`, or `.proc` bodies. The converter is normalizing existing margin intent, not inventing structural nesting.

### 6.4 Operation Casing

After locating the operation field:

* If it is a recognized 6502 machine instruction, convert it to uppercase.
* If it is a pseudo-op, assembler directive, macro call, or alias call, convert it to lowercase.
* Preserve labels and operands unless they are part of a controlled macro-name conversion.

Opcode recognition must use an explicit lookup table rather than assumptions based on word length or spelling.

The initial opcode table should match the project’s `--cpu 6502` setting. Opcodes from the 65C02, 65816, or undocumented instruction sets should require an explicit dialect option.

### 6.5 Macro and Alias Safety

Because macro and alias identifiers may be case-sensitive, the formatter needs a preliminary symbol-discovery pass.

That pass should collect:

* Macro definitions.
* Alias definitions, if supported.
* Macro invocations.
* References that occur in operation position.
* Original spellings of every discovered identifier.

When a macro or alias operation is converted to lowercase, its definition must be converted to the same spelling.

Before making the change, detect case-folding collisions. For example, distinct definitions named `COPYBYTE` and `copybyte` cannot both be converted safely to `copybyte`.

On collision or unresolved ambiguity, report the line and leave the identifier unchanged rather than silently damaging the source.

Ordinary labels and procedure names should remain unchanged unless a future option explicitly requests symbol normalization.

### 6.6 Commas

Within the code portion of a line:

* Remove all whitespace immediately before a comma.
* Insert exactly one space after a comma.
* Do not insert a trailing space when the comma is immediately followed by the inline comment delimiter or end of line.
* Do not modify commas inside quoted strings or comments.

Examples affected by this rule include macro arguments, indexed addressing, and data declarations.

### 6.7 Inline Comments

Format the code portion first and remove its trailing whitespace.

Then place the comment as follows:

* When the formatted code ends before `COMMENT_INDENT`, pad with spaces so the semicolon begins exactly at `COMMENT_INDENT`.
* When the code reaches or passes `COMMENT_INDENT`, append `MIN_COMMENT_GAP` spaces and then the comment.
* Never move code backward or wrap code merely to align a comment.
* Preserve the comment text exactly, including whether it begins with `;` or `;;`.

Visual columns should be calculated after tabs have been converted to spaces.

## 7. Processing Pipeline

The formatter should use these phases:

1. Read the file without changing its encoding or newline convention.
2. Scan all lines and collect macro or alias definitions.
3. Detect case-folding collisions.
4. Lex each line into indentation, label, operation, operands, and comment.
5. Determine the line’s original margin status.
6. Apply operation casing.
7. Normalize commas in the operand region.
8. Reconstruct the code portion.
9. Apply left-margin or `INDENT_SIZE` indentation.
10. Place standalone or inline comments.
11. Remove trailing whitespace.
12. Write to a temporary file.
13. Validate the result before replacing the original.

## 8. Safety Modes

The command-line interface should support:

* Standard output mode.
* Check-only mode that reports files needing changes.
* Unified-diff mode.
* In-place mode.
* Optional backup creation.
* Verbose diagnostics for ambiguous lines.
* A strict mode that refuses to write when parsing is uncertain.

The default should not overwrite files.

## 9. Validation

### Golden Tests

Create expected-output fixtures using representative lines from the uploaded source:

* Indented and margin-level directives.
* Mixed-case opcodes.
* Mixed-case `.MACRO` and `.ENDMacro`.
* Local labels.
* Global labels.
* Label-plus-pseudo-op lines.
* Label-plus-macro-call lines.
* Indexed operands such as `(TMP_PTR),Y`.
* Multi-argument macro calls.
* Inline comments before and after `COMMENT_INDENT`.
* Long code lines.
* Strings containing punctuation.
* Consecutive standalone comments.

### Required Properties

The completed formatter must satisfy:

* Formatting a file twice produces exactly the same result.
* Line count remains unchanged.
* String contents remain byte-for-byte unchanged.
* Comment contents remain byte-for-byte unchanged apart from leading placement.
* Labels and operands remain unchanged unless covered by an explicit symbol conversion.
* Every indented code line uses exactly `INDENT_SIZE` spaces.
* No code-region comma has preceding whitespace.
* Every code-region comma has one following space.
* Every recognized 6502 opcode is uppercase.
* Every recognized pseudo-op is lowercase.

### Assembly Validation

For the supplied project:

1. Build the original source and retain `bios.bin`.
2. Format a copy of the assembly sources.
3. Build the formatted copy.
4. Compare the generated ROM images byte-for-byte.
5. Confirm that exported symbols and vector addresses remain unchanged.

Object files containing debug source positions are not suitable for direct equality testing; the final ROM image is the stronger semantic comparison.

## 10. Error Handling

The formatter should report and avoid modifying lines containing:

* Unterminated quoted strings.
* Unknown lexical constructs.
* Ambiguous operation fields.
* Case-folding symbol collisions.
* Macro definitions that cannot be paired with their calls.
* Unsupported CPU-dialect instructions.
* Invalid text encoding.

Diagnostics should include the filename, line number, original line, and reason.

## 11. Recommended Implementation Milestones

### Milestone 1: Lexer

Implement safe separation of code, quoted values, and comments.

### Milestone 2: Line Structure

Recognize labels, assignments, operation fields, and operands.

### Milestone 3: Basic Formatting

Implement indentation, comma spacing, and inline-comment placement without case conversion.

### Milestone 4: Opcode and Directive Casing

Add the official 6502 opcode table and ca65 pseudo-op recognition.

### Milestone 5: Macro and Alias Analysis

Add definition discovery, consistent renaming, collision detection, and diagnostics.

### Milestone 6: Corpus Tests

Convert the uploaded source into golden test fixtures and confirm idempotence.

### Milestone 7: Build Equivalence

Assemble the original and formatted projects and compare the resulting ROM images.

### Milestone 8: Command-Line Safety

Add check, diff, output, backup, strict, and in-place modes.

## 12. Acceptance Standard

The converter is complete when it can format the entire assembly corpus, produce an identical ROM image, generate no ca65 errors, remain unchanged on a second formatting pass, and report every ambiguous or unsafe case rather than guessing.


### 6.5 Valid MOS 6502 Opcodes

For formatting purposes, an opcode is recognized by its mnemonic. The default opcode table must contain only the 56 documented NMOS MOS 6502 instruction mnemonics:

| Category                | Mnemonics                                              |
| ----------------------- | ------------------------------------------------------ |
| Arithmetic              | `ADC`, `SBC`                                           |
| Logic                   | `AND`, `BIT`, `EOR`, `ORA`                             |
| Shift and rotate        | `ASL`, `LSR`, `ROL`, `ROR`                             |
| Branch                  | `BCC`, `BCS`, `BEQ`, `BMI`, `BNE`, `BPL`, `BVC`, `BVS` |
| Compare                 | `CMP`, `CPX`, `CPY`                                    |
| Increment and decrement | `DEC`, `DEX`, `DEY`, `INC`, `INX`, `INY`               |
| Load and store          | `LDA`, `LDX`, `LDY`, `STA`, `STX`, `STY`               |
| Register transfer       | `TAX`, `TAY`, `TSX`, `TXA`, `TXS`, `TYA`               |
| Stack                   | `PHA`, `PHP`, `PLA`, `PLP`                             |
| Control flow            | `BRK`, `JMP`, `JSR`, `NOP`, `RTI`, `RTS`               |
| Processor flags         | `CLC`, `CLD`, `CLI`, `CLV`, `SEC`, `SED`, `SEI`        |

Opcode comparison should be case-insensitive, but a recognized opcode must always be emitted in uppercase.

The table should be stored as an explicit immutable set. The formatter must not infer that an identifier is an opcode from its length, spelling, operand syntax, or similarity to another mnemonic.

The default table must exclude:

* Undocumented NMOS instructions such as `LAX`, `SAX`, `DCP`, `ISC`, `SLO`, and `RLA`.
* 65C02 additions such as `BRA`, `PHX`, `PHY`, `PLX`, `PLY`, `STZ`, `TRB`, and `TSB`.
* Processor-specific instructions from the 65816, 6502DTV, HuC6280, 4510, and other extended families.
* User macros or aliases whose names happen to resemble instruction mnemonics.

This matches ca65’s `6502` CPU mode, which enables the base 6502 instruction set while disabling 65SC02, 65C02, and 65816 extensions. cc65 distinguishes this legal NMOS instruction set from its separate `6502X` mode, which includes undocumented instructions.

A future dialect option may select a different opcode set, but the selected set must replace or extend the base table explicitly. The formatter must never silently enable instructions from another processor family.

Opcode recognition determines casing only. It does not, by itself, validate whether the operand uses an addressing mode supported by that particular instruction. Addressing-mode validation should be a separate optional feature so the formatter does not become an assembler.


## 7 Bug fixes
### 7.1 Scroping rules around labels.

Scoping rules around a label are not understood. This causes a failure

```
.repeat ::SCREEN_ROWS, I
```

### 7.2 ";ignore-next-line' is not honored.

There are some lines of code that the formatter is not capable of dealing with.

if there is a comment (starting anywhere on the line) with the next *anywhere* in the comment of "ignore-next-line" then the next line should not be checked or validated at all.

