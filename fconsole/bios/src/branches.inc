; quick and dirty macro so we dont haev to keep fixing 65c02 code on the fly
.macro stz dest
    PHA
    LDA #$00
    STA dest
    PLA
.endmacro

; ============================================================================
; ca65 Synthetic Branching and Relational Macro Suite
; ============================================================================
;
; This file provides:
;
;   1. Short unsigned branch aliases
;   2. Short signed relational branches
;   3. Combined CMP-immediate-and-branch helpers
;   4. Long conditional jumps implemented with an inverse branch plus JMP
;
;
; SHORT-BRANCH RANGE
; ------------------
; Macros in sections 1 through 3 ultimately emit ordinary 6502 relative branch
; instructions. Their target must therefore be within the normal signed 8-bit
; branch displacement:
;
;       -128 to +127 bytes from the instruction following the branch
;
; Use the long-jump macros in section 4 when the destination may be farther
; away.
;
;
; UNSIGNED COMPARISONS
; --------------------
; Unsigned comparisons may follow CMP, CPX, or CPY.
;
; After:
;
;       CMP operand
;
; the relevant unsigned relationships are:
;
;       Z = 1       equal
;       Z = 0       not equal
;       C = 0       less than
;       C = 1       greater than or equal
;       C = 1,Z = 0 greater than
;       C = 0,Z = * less than
;       Z = 1       equal
;
; Values are interpreted as unsigned bytes in the range 0 through 255.
;
;
; SIGNED COMPARISONS
; ------------------
; Signed relational branches require valid N and V flags from a subtraction.
;
; CMP, CPX, and CPY do not modify V, so they are not sufficient by themselves
; for a reliable signed comparison.
;
; Establish signed-comparison flags with binary subtraction:
;
;       CLD
;       SEC
;       LDA left_operand
;       SBC right_operand
;       sblt target
;
; The subtraction result itself does not need to be preserved. The signed
; relationship is represented by N and V:
;
;       N != V      signed less than
;       N == V      signed greater than or equal
;
; Values are interpreted as signed two's-complement bytes in the range
; -128 through +127.
;
;
; REGISTER AND FLAG EFFECTS
; -------------------------
; The branch-only macros do not modify A, X, Y, or the processor flags.
;
; The combined if_a_* macros execute CMP and therefore update:
;
;       N, Z, and C
;
; CMP does not modify V.
;
; ============================================================================


; ----------------------------------------------------------------------------
; 1. UNSIGNED CONDITIONAL BRANCHES
; ----------------------------------------------------------------------------
;
; These macros inspect flags previously established by CMP, CPX, CPY, or
; another operation that produces equivalent Z and C flag meanings.
;
; They emit ordinary relative branches, so the destination must be within
; normal 6502 branch range.
; ----------------------------------------------------------------------------


; ----------------------------------------------------------------------------
; beq_alias target
;
; Branch when the compared values are equal.
;
; Condition:
;       Z = 1
;
; Equivalent instruction:
;       BEQ target
;
; Typical use:
;       LDA value
;       CMP #expected
;       beq_alias matched
; ----------------------------------------------------------------------------

.macro beq_alias target
    BEQ target
.endmacro


; ----------------------------------------------------------------------------
; bne_alias target
;
; Branch when the compared values are not equal.
;
; Condition:
;       Z = 0
;
; Equivalent instruction:
;       BNE target
; ----------------------------------------------------------------------------

.macro bne_alias target
    BNE target
.endmacro


; ----------------------------------------------------------------------------
; blt target
;
; Branch when the left operand is less than the right operand, interpreting
; both operands as unsigned bytes.
;
; Condition after CMP/CPX/CPY:
;       C = 0
;
; Equivalent instruction:
;       BCC target
;
; Example:
;       LDA #10
;       CMP #20
;       blt less_than             ; Taken
; ----------------------------------------------------------------------------

.macro blt target
    BCC target
.endmacro


; ----------------------------------------------------------------------------
; bge target
;
; Branch when the left operand is greater than or equal to the right operand,
; interpreting both operands as unsigned bytes.
;
; Condition after CMP/CPX/CPY:
;       C = 1
;
; Equivalent instruction:
;       BCS target
; ----------------------------------------------------------------------------

.macro bge target
    BCS target
.endmacro


; ----------------------------------------------------------------------------
; bgt target
;
; Branch when the left operand is strictly greater than the right operand,
; interpreting both operands as unsigned bytes.
;
; Condition after CMP/CPX/CPY:
;       C = 1 and Z = 0
;
; Equality is explicitly excluded before testing carry.
;
; Expansion:
;       BEQ internal_skip
;       BCS target
;   internal_skip:
;
; Size:
;       4 bytes
;
; Target restriction:
;       target must be in range of the generated BCS instruction.
; ----------------------------------------------------------------------------

.macro bgt target
    .local @skip

    BEQ @skip
    BCS target

@skip:
.endmacro


; ----------------------------------------------------------------------------
; ble target
;
; Branch when the left operand is less than or equal to the right operand,
; interpreting both operands as unsigned bytes.
;
; Condition after CMP/CPX/CPY:
;       Z = 1 or C = 0
;
; Expansion:
;       BEQ target
;       BCC target
;
; Size:
;       4 bytes
;
; Target restriction:
;       target must be in range of both generated branch instructions.
; ----------------------------------------------------------------------------

.macro ble target
    BEQ target
    BCC target
.endmacro


; ----------------------------------------------------------------------------
; 2. SIGNED CONDITIONAL BRANCHES
; ----------------------------------------------------------------------------
;
; These macros interpret the operands as signed two's-complement bytes.
;
; REQUIRED PRECONDITION
; ---------------------
; N and V must describe the result of:
;
;       left_operand - right_operand
;
; Normally establish these flags using:
;
;       CLD
;       SEC
;       LDA left_operand
;       SBC right_operand
;
; Do not rely on CMP, CPX, or CPY alone because those instructions leave V
; unchanged.
;
; These macros emit relative branches. The target must be within normal 6502
; branch range from every generated branch that can reach it.
; ----------------------------------------------------------------------------


; ----------------------------------------------------------------------------
; sbge target
;
; Branch when:
;
;       signed left_operand >= signed right_operand
;
; Signed condition:
;       N == V
;
; Truth table:
;
;       V   N   Result
;       -------------------------------
;       0   0   branch
;       0   1   do not branch
;       1   0   do not branch
;       1   1   branch
;
; Inputs:
;       N and V from a preceding binary subtraction
;
; Preserves:
;       A, X, Y, and all processor flags
;
; Target restriction:
;       target must be in relative range of the generated BMI or BPL branch.
; ----------------------------------------------------------------------------

.macro sbge target
    .local @no_overflow, @done

    BVC @no_overflow

    ; Overflow occurred.
    ; N=1,V=1 means N == V, so the signed result is >=.
    BMI target

    ; N=0,V=1 means N != V, so the signed result is <.
    BPL @done

@no_overflow:
; V=0. N=0 means N == V, so the signed result is >=.
    BPL target

@done:
.endmacro


; ----------------------------------------------------------------------------
; sblt target
;
; Branch when:
;
;       signed left_operand < signed right_operand
;
; Signed condition:
;       N != V
;
; This is strictly less-than. Equality does not branch.
;
; Truth table:
;
;       V   N   Result
;       -------------------------------
;       0   0   do not branch
;       0   1   branch
;       1   0   branch
;       1   1   do not branch
;
; Inputs:
;       N and V from a preceding binary subtraction
;
; Preserves:
;       A, X, Y, and all processor flags
;
; Target restriction:
;       target must be in relative range of the generated BPL or BMI branch.
; ----------------------------------------------------------------------------

.macro sblt target
    .local @no_overflow, @done

    BVC @no_overflow

    ; Overflow occurred.
    ; N=0,V=1 means N != V, so the signed result is <.
    BPL target

    ; N=1,V=1 means N == V, so the signed result is >=.
    BMI @done

@no_overflow:
; V=0. N=1 means N != V, so the signed result is <.
    BMI target

@done:
.endmacro

; ----------------------------------------------------------------------------
; sble target
;
; Branch when:
;
;       signed left_operand <= signed right_operand
;
; Required setup:
;
;       CLD
;       SEC
;       LDA left_operand
;       SBC right_operand
;       sble target
;
; Signed condition:
;
;       Z = 1 or N != V
;
; CMP, CPX, and CPY are not sufficient because they do not update V.
;
; Preserves:
;       A, X, Y, and all processor flags
;
; Target restriction:
;       target must be within relative branch range of both the generated
;       BEQ instruction and the branches generated by sblt.
; ----------------------------------------------------------------------------

.macro sble target
    BEQ target
    sblt target
.endmacro

; ----------------------------------------------------------------------------
; 3. COMBINED COMPARE-AND-BRANCH HELPERS
; ----------------------------------------------------------------------------
;
; These macros compare A against an immediate 8-bit value and then perform an
; unsigned conditional branch.
;
; Syntax:
;
;       if_a_<relation> value, target
;
; Example:
;
;       LDA item_count
;       if_a_ge 10, enough_items
;
; The value argument is written without '#'. Each macro supplies the immediate
; addressing marker itself:
;
;       Correct:    if_a_eq $20, target
;       Incorrect:  if_a_eq #$20, target
;
; Effects:
;       A is preserved.
;       X and Y are preserved.
;       N, Z, and C are replaced by the result of CMP.
;       V is unchanged.
;
; These are unsigned comparisons. Their targets must be within ordinary branch
; range.
; ----------------------------------------------------------------------------


; ----------------------------------------------------------------------------
; if_a_eq value, target
;
; Compare A with an immediate value and branch when A == value.
;
; Condition:
;       Z = 1
; ----------------------------------------------------------------------------

.macro if_a_eq value, target
    CMP #value
    BEQ target
.endmacro


; ----------------------------------------------------------------------------
; if_a_ne value, target
;
; Compare A with an immediate value and branch when A != value.
;
; Condition:
;       Z = 0
; ----------------------------------------------------------------------------

.macro if_a_ne value, target
    CMP #value
    BNE target
.endmacro


; ----------------------------------------------------------------------------
; if_a_lt value, target
;
; Compare A with an immediate value and branch when A < value, using unsigned
; byte ordering.
;
; Condition:
;       C = 0
; ----------------------------------------------------------------------------

.macro if_a_lt value, target
    CMP #value
    BCC target
.endmacro


; ----------------------------------------------------------------------------
; if_a_ge value, target
;
; Compare A with an immediate value and branch when A >= value, using unsigned
; byte ordering.
;
; Condition:
;       C = 1
; ----------------------------------------------------------------------------

.macro if_a_ge value, target
    CMP #value
    BCS target
.endmacro


; ----------------------------------------------------------------------------
; if_a_gt value, target
;
; Compare A with an immediate value and branch when A > value, using unsigned
; byte ordering.
;
; Condition:
;       C = 1 and Z = 0
;
; Expansion:
;       CMP #value
;       BEQ internal_skip
;       BCS target
;   internal_skip:
;
; Target restriction:
;       target must be in range of the generated BCS instruction.
; ----------------------------------------------------------------------------

.macro if_a_gt value, target
    .local @skip

    CMP #value
    BEQ @skip
    BCS target

@skip:
.endmacro


; ----------------------------------------------------------------------------
; if_a_le value, target
;
; Compare A with an immediate value and branch when A <= value, using unsigned
; byte ordering.
;
; Condition:
;       Z = 1 or C = 0
;
; Expansion:
;       CMP #value
;       BEQ target
;       BCC target
;
; Target restriction:
;       target must be in range of both generated branch instructions.
; ----------------------------------------------------------------------------

.macro if_a_le value, target
    CMP #value
    BEQ target
    BCC target
.endmacro


; ============================================================================
; 4. SMART LONG CONDITIONAL JUMPS
; ============================================================================
;
; The 6502 has no native long conditional branch. These macros synthesize one
; by branching over an absolute JMP when the condition is false:
;
;       inverse_condition internal_skip
;       JMP target
;   internal_skip:
;
; Properties:
;
;   - The destination is not limited to relative branch range.
;   - The destination must still be reachable by an absolute JMP in the
;     current 16-bit address space.
;   - A, X, Y, and processor flags are preserved.
;   - Each macro normally emits 5 bytes.
;
; When the destination is already in ordinary branch range, a native branch
; uses only 2 bytes and is generally faster. check_branch_distance emits an
; assembly-time optimization message for that case.
;
; DISTANCE-CHECK LIMITATION
; -------------------------
; The target expression must be resolvable as a constant when ca65 evaluates
; check_branch_distance. This generally works for known labels in the same
; segment, especially backward targets.
;
; An unresolved, imported, or otherwise non-constant target may cause ca65 to
; report:
;
;       Constant expression expected
;
; In such cases, remove or disable the distance check for that invocation while
; retaining the long-jump implementation.
; ============================================================================


; ----------------------------------------------------------------------------
; check_branch_distance target_label, macro_name, short_name
;
; Internal diagnostic helper used by the long conditional jump macros.
;
; Parameters:
;
;   target_label
;       Destination whose displacement is checked.
;
;   macro_name
;       String used to identify the current long-jump macro in the diagnostic.
;
;   short_name
;       String naming the equivalent native relative branch.
;
; Behavior:
;
;   - Produces an assembly error when target_label is blank.
;   - Emits an optimization message when the target falls within the native
;     branch displacement range.
;   - Emits no code.
;
; The displacement is measured from the address immediately after a normal
; two-byte relative branch instruction.
; ----------------------------------------------------------------------------

.macro check_branch_distance target_label, macro_name, short_name
    .ifblank target_label
    .error "Missing target label for long branch macro"
    .else
    .if (target_label - (* + 2)) >= -128 .and  (target_label - (* + 2)) <= 127
    .out .sprintf("OPTIMIZATION WARNING: %s to '%s' is in range! Use %s instead to save 3 bytes and cycles.", macro_name, .string(target_label), short_name)
    .endif
    .endif
.endmacro

; ----------------------------------------------------------------------------
; jeq target
;
; Long jump when the compared values are equal.
;
; Condition:
;       Z = 1
;
; Equivalent short branch:
;       BEQ target
;
; Expansion:
;       BNE internal_skip
;       JMP target
;   internal_skip:
; ----------------------------------------------------------------------------

.macro jeq target
    check_branch_distance target, "JEQ", "BEQ"
    .local @skip

    BNE @skip
    JMP target

@skip:
.endmacro


; ----------------------------------------------------------------------------
; jne target
;
; Long jump when the compared values are not equal.
;
; Condition:
;       Z = 0
;
; Equivalent short branch:
;       BNE target
;
; Expansion:
;       BEQ internal_skip
;       JMP target
;   internal_skip:
; ----------------------------------------------------------------------------

.macro jne target
    check_branch_distance target, "JNE", "BNE"
    .local @skip

    BEQ @skip
    JMP target

@skip:
.endmacro


; ----------------------------------------------------------------------------
; jlt target
;
; Long jump when the left operand is less than the right operand, interpreting
; both operands as unsigned bytes.
;
; Condition after CMP/CPX/CPY:
;       C = 0
;
; Equivalent short branch:
;       BCC target
;
; Expansion:
;       BCS internal_skip
;       JMP target
;   internal_skip:
; ----------------------------------------------------------------------------

.macro jlt target
    check_branch_distance target, "JLT", "BCC"
    .local @skip

    BCS @skip
    JMP target

@skip:
.endmacro


; ----------------------------------------------------------------------------
; jge target
;
; Long jump when the left operand is greater than or equal to the right operand,
; interpreting both operands as unsigned bytes.
;
; Condition after CMP/CPX/CPY:
;       C = 1
;
; Equivalent short branch:
;       BCS target
;
; Expansion:
;       BCC internal_skip
;       JMP target
;   internal_skip:
; ----------------------------------------------------------------------------

.macro jge target
    check_branch_distance target, "JGE", "BCS"
    .local @skip

    BCC @skip
    JMP target

@skip:
.endmacro
