; ============================================================================
; ca65 Synthetic Branching and Relational Macro Suite
; ============================================================================
; Usage Notes:
; - Execute CMP, CPX, or CPY before calling any of these branch macros.
; - Unsigned operations treat numbers as 0..255.
; - Signed operations treat numbers as -128..+127 (using N and V flags).
; ============================================================================

; ----------------------------------------------------------------------------
; 1. UNSIGNED CONDITIONAL BRANCHES
; ----------------------------------------------------------------------------

;; Equal (==)
.macro BEQ_ALIAS label
    BEQ label
.endmacro

;; Not Equal (!=)
.macro BNE_ALIAS label
    BNE label
.endmacro

;; Less Than (<)
.macro BLT label
    BCC label
.endmacro

;; Greater Than or Equal (>=)
.macro BGE label
    BCS label
.endmacro

;; Greater Than (>)
.macro BGT label
    .local @skip
    BEQ @skip
    BCS label
@skip:
.endmacro

;; Less Than or Equal (<=)
.macro BLE label
    BEQ label
    BCC label
.endmacro


; ----------------------------------------------------------------------------
; 2. SIGNED CONDITIONAL BRANCHES
; ----------------------------------------------------------------------------

;; Signed Greater Than or Equal (>=)
.macro SBGE label
    .local @skip
    BMI @skip
    BVC label       ; Positive result without overflow -> >=
@skip:
.endmacro

;; Signed Less Than (<)
.macro SBLT label
    .local @skip
    BPL @skip
    BVS label       ; Negative result without overflow -> <
@skip:
.endmacro


; ----------------------------------------------------------------------------
; 3. COMBINED COMPARE & BRANCH HELPER MACROS
; ----------------------------------------------------------------------------
; These macros take care of both the CMP instruction and the branch choice,
; allowing for clear 1-line comparisons.

;; Compare A with immediate value and branch if A == val
.macro IF_A_EQ val, label
    CMP #val
    BEQ label
.endmacro

;; Compare A with immediate value and branch if A != val
.macro IF_A_NE val, label
    CMP #val
    BNE label
.endmacro

;; Compare A with immediate value and branch if A < val (Unsigned)
.macro IF_A_LT val, label
    CMP #val
    BCC label
.endmacro

;; Compare A with immediate value and branch if A >= val (Unsigned)
.macro IF_A_GE val, label
    CMP #val
    BCS label
.endmacro

;; Compare A with immediate value and branch if A > val (Unsigned)
.macro IF_A_GT val, label
    .local @skip
    CMP #val
    BEQ @skip
    BCS label
@skip:
.endmacro

;; Compare A with immediate value and branch if A <= val (Unsigned)
.macro IF_A_LE val, label
    CMP #val
    BEQ label
    BCC label
.endmacro


; ============================================================================
; Smart Long Branch Macros with Distance Checks
; ============================================================================

;; Helper Macro: Emits warning if destination is within standard branch range (-128 to +127)
.macro CHECK_BRANCH_DISTANCE target_label, macro_name, short_name
    .ifblank target_label
        .error "Missing target label for long branch macro"
    .else
        ; Check if the target distance can fit in a signed 8-bit offset (-128 to +127)
        ; Note: 2 bytes are added to account for the branch instruction size itself
        .if (target_label - (* + 2)) >= -128 .and (target_label - (* + 2)) <= 127
            .out .sprintf("OPTIMIZATION WARNING: %s to '%s' is in range! Use %s instead to save 3 bytes and cycles.", macro_name, .string(target_label), short_name)
        .endif
    .endif
.endmacro


;; JEQ - Jump if Equal (Z == 1)
.macro JEQ label
    CHECK_BRANCH_DISTANCE label, "JEQ", "BEQ"
    .local @skip
    BNE @skip
    JMP label
@skip:
.endmacro

;; JNE - Jump if Not Equal (Z == 0)
.macro JNE label
    CHECK_BRANCH_DISTANCE label, "JNE", "BNE"
    .local @skip
    BEQ @skip
    JMP label
@skip:
.endmacro

;; JLT - Jump if Less Than / Carry Clear (Unsigned <)
.macro JLT label
    CHECK_BRANCH_DISTANCE label, "JLT", "BCC"
    .local @skip
    BCS @skip
    JMP label
@skip:
.endmacro

;; JGE - Jump if Greater or Equal / Carry Set (Unsigned >=)
.macro JGE label
    CHECK_BRANCH_DISTANCE label, "JGE", "BCS"
    .local @skip
    BCC @skip
    JMP label
@skip:
.endmacro
