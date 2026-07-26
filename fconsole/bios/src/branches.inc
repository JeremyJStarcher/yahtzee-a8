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
.macro beq_alias label
    BEQ label
.endmacro

;; Not Equal (!=)
.macro bne_alias label
    BNE label
.endmacro

;; Less Than (<)
.macro blt label
    BCC label
.endmacro

;; Greater Than or Equal (>=)
.macro bge label
    BCS label
.endmacro

;; Greater Than (>)
.macro bgt label
    .local @skip
    BEQ @skip
    BCS label
@skip:
.endmacro

;; Less Than or Equal (<=)
.macro ble label
    BEQ label
    BCC label
.endmacro


; ----------------------------------------------------------------------------
; 2. SIGNED CONDITIONAL BRANCHES
; ----------------------------------------------------------------------------

;; Signed Greater Than or Equal (>=)
.macro sbge label
    .local @skip
    BMI @skip
    BVC label                           ; Positive result without overflow -> >=
@skip:
.endmacro

;; Signed Less Than (<)
.macro sblt label
    .local @skip
    BPL @skip
    BVS label                           ; Negative result without overflow -> <
@skip:
.endmacro


; ----------------------------------------------------------------------------
; 3. COMBINED COMPARE & BRANCH HELPER MACROS
; ----------------------------------------------------------------------------
; These macros take care of both the CMP instruction and the branch choice,
; allowing for clear 1-line comparisons.

;; Compare A with immediate value and branch if A == val
.macro if_a_eq val, label
    CMP #val
    BEQ label
.endmacro

;; Compare A with immediate value and branch if A != val
.macro if_a_ne val, label
    CMP #val
    BNE label
.endmacro

;; Compare A with immediate value and branch if A < val (Unsigned)
.macro if_a_lt val, label
    CMP #val
    BCC label
.endmacro

;; Compare A with immediate value and branch if A >= val (Unsigned)
.macro if_a_ge val, label
    CMP #val
    BCS label
.endmacro

;; Compare A with immediate value and branch if A > val (Unsigned)
.macro if_a_gt val, label
    .local @skip
    CMP #val
    BEQ @skip
    BCS label
@skip:
.endmacro

;; Compare A with immediate value and branch if A <= val (Unsigned)
.macro if_a_le val, label
    CMP #val
    BEQ label
    BCC label
.endmacro


; ============================================================================
; Smart Long Branch Macros with Distance Checks
; ============================================================================

;; Helper Macro: Emits warning if destination is within standard branch range (-128 to +127)
.macro check_branch_distance target_label, macro_name, short_name
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
.macro jeq label
    check_branch_distance label, "JEQ", "BEQ"
    .local @skip
    BNE @skip
    JMP label
@skip:
.endmacro

;; JNE - Jump if Not Equal (Z == 0)
.macro jne label
    check_branch_distance label, "JNE", "BNE"
    .local @skip
    BEQ @skip
    JMP label
@skip:
.endmacro

;; JLT - Jump if Less Than / Carry Clear (Unsigned <)
.macro jlt label
    check_branch_distance label, "JLT", "BCC"
    .local @skip
    BCS @skip
    JMP label
@skip:
.endmacro

;; JGE - Jump if Greater or Equal / Carry Set (Unsigned >=)
.macro jge label
    check_branch_distance label, "JGE", "BCS"
    .local @skip
    BCC @skip
    JMP label
@skip:
.endmacro
