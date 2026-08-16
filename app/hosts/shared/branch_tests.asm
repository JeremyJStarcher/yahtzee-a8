; ============================================================================
; Branch Macro Test Suite
; ============================================================================
;
; Requires:
;
; expected_taken:
;   0 = branch should not be taken
;   1 = branch should be taken
; ============================================================================

TEST_FAIL_COLOR = $A3

BRANCH_NOT_TAKEN = 0
BRANCH_TAKEN     = 1

; ----------------------------------------------------------------------------
; Test result strings
; ----------------------------------------------------------------------------

next_line: pstring2 {CHAR_NL}

test_branch_taken:
    pstring "BRANCH TAKEN"

test_branch_not_taken:
    pstring "BRANCH NOT TAKEN"

passed_msg: pstring2 {"  PASSED", CHAR_NL}
failed_msg: pstring2 {"  FAILED", CHAR_NL}
; NOTE: zero-page scratch (fail_flag, branch_test_actual) is allocated in a
; single consolidated ZEROPAGE section at the top level (fconsole.asm).

.segment "CODE"

.macro hoststrout ptr
    LDX #<ptr
    LDA #>ptr
    JSR JTSTROUT
.endmacro


; ============================================================================
; Mark the current test as failed
; ============================================================================

.macro mark_branch_test_failed
    LDA #$01
    STA fail_flag
.endmacro

; ============================================================================
; Test a branch macro that expects flags to have been set by CMP
;
; Example:
;   create_branch_test "BLT 0,1", blt, 0, 1, BRANCH_TAKEN
; ============================================================================

.macro create_branch_test test_name, macroopcode, val1, val2, expected_taken
    .local test_string
    .local test_start
    .local did_branch
    .local not_taken_ok
    .local taken_ok
    .local test_done
    .local exit2

    ; Skip the inline Pascal string.
    JMP test_start

test_string:
    pstring test_name

test_start:
    hoststrout test_string

    ; Establish flags through an unsigned compare.
    LDA #val1
    CMP #val2

    macroopcode did_branch

    ; ------------------------------------------------------------------------
    ; Actual result: branch not taken
    ; ------------------------------------------------------------------------

    LDA #expected_taken
    BEQ not_taken_ok

    mark_branch_test_failed

not_taken_ok:
    hoststrout test_branch_not_taken
    JMP test_done

did_branch:
; ------------------------------------------------------------------------
; Actual result: branch taken
; ------------------------------------------------------------------------

    LDA #expected_taken
    BNE taken_ok

    mark_branch_test_failed

taken_ok:
    hoststrout test_branch_taken

test_done:
    LDA fail_flag
    BEQ exit2
    hoststrout failed_msg
    JMP freeze_it
exit2:
    hoststrout passed_msg
.endmacro


; ============================================================================
; Test one of the combined "if_a_*" macros
;
; The tested macro performs its own CMP.
;
; Example:
;   create_a_compare_test "A LT 0,1", if_a_lt, 0, 1, BRANCH_TAKEN
; ============================================================================

.macro create_a_compare_test test_name, macroopcode, a_value, compare_value, expected_taken
    .local test_string
    .local test_start
    .local did_branch
    .local not_taken_ok
    .local taken_ok
    .local test_done
    .local exit2

    JMP test_start

test_string:
    pstring test_name

test_start:
    hoststrout test_string

    LDA #a_value
    macroopcode compare_value, did_branch

    ; ------------------------------------------------------------------------
    ; Actual result: branch not taken
    ; ------------------------------------------------------------------------

    LDA #expected_taken
    BEQ not_taken_ok

    mark_branch_test_failed

not_taken_ok:
    hoststrout test_branch_not_taken
    JMP test_done

did_branch:
; ------------------------------------------------------------------------
; Actual result: branch taken
; ------------------------------------------------------------------------

    LDA #expected_taken
    BNE taken_ok

    mark_branch_test_failed

taken_ok:
    hoststrout test_branch_taken

test_done:
    LDA fail_flag
    BEQ exit2
    hoststrout failed_msg
    JMP freeze_it
exit2:
    hoststrout passed_msg
.endmacro


; ============================================================================
; Test a signed branch macro
;
; IMPORTANT:
;   CMP does not modify V, so signed comparisons cannot reliably use CMP.
;   SEC/SBC is used here to establish N and V for:
;
;       signed_lhs - signed_rhs
;
; Example:
;   create_signed_branch_test "SBLT -1,0", sblt, $FF, $00, BRANCH_TAKEN
; ============================================================================

.macro create_signed_branch_test test_name, macroopcode, signed_lhs, signed_rhs, expected_taken
    .local test_string
    .local test_start
    .local did_branch
    .local not_taken_ok
    .local taken_ok
    .local test_done
    .local exit2

    JMP test_start

test_string:
    pstring test_name

test_start:
    hoststrout test_string

    ; Ensure binary arithmetic.
    CLD

    ; Establish N and V using a real subtraction.
    SEC
    LDA #signed_lhs
    SBC #signed_rhs

    macroopcode did_branch

    ; ------------------------------------------------------------------------
    ; Actual result: branch not taken
    ; ------------------------------------------------------------------------

    LDA #expected_taken
    BEQ not_taken_ok

    mark_branch_test_failed

not_taken_ok:
    hoststrout test_branch_not_taken
    JMP test_done

did_branch:
; ------------------------------------------------------------------------
; Actual result: branch taken
; ------------------------------------------------------------------------

    LDA #expected_taken
    BNE taken_ok

    mark_branch_test_failed

taken_ok:
    hoststrout test_branch_taken

test_done:
    LDA fail_flag
    BEQ exit2
    hoststrout failed_msg
    JMP freeze_it
exit2:
    hoststrout passed_msg
.endmacro


; ============================================================================
; Test a smart long-jump macro
;
; The destination is deliberately placed more than 127 bytes backward so the
; check_branch_distance macro recognizes this as a legitimate long jump.
;
; Example:
;   create_long_branch_test "JEQ 1,1", jeq, 1, 1, BRANCH_TAKEN
; ============================================================================

.macro create_long_branch_test test_name, macroopcode, val1, val2, expected_taken
    .local test_string
    .local test_start
    .local far_branch_target
    .local evaluate_result
    .local actual_taken
    .local not_taken_ok
    .local taken_ok
    .local test_done
    .local exit2

    ; Normal execution skips the backward branch target and padding.
    JMP test_start

far_branch_target:
    LDA #$01
    STA branch_test_actual
    JMP evaluate_result

    ; Force far_branch_target outside ordinary relative branch range.
    .repeat 132
    NOP
    .endrepeat

test_string:
    pstring test_name

test_start:
    hoststrout test_string

    LDA #$00
    STA branch_test_actual

    LDA #val1
    CMP #val2

    macroopcode far_branch_target

evaluate_result:
    LDA branch_test_actual
    BNE actual_taken

    ; ------------------------------------------------------------------------
    ; Actual result: branch not taken
    ; ------------------------------------------------------------------------

    LDA #expected_taken
    BEQ not_taken_ok

    mark_branch_test_failed

not_taken_ok:
    hoststrout test_branch_not_taken
    JMP test_done

actual_taken:
; ------------------------------------------------------------------------
; Actual result: branch taken
; ------------------------------------------------------------------------

    LDA #expected_taken
    BNE taken_ok

    mark_branch_test_failed

taken_ok:
    hoststrout test_branch_taken

test_done:
    LDA fail_flag
    BEQ exit2
    hoststrout failed_msg
    JMP freeze_it
exit2:
    hoststrout passed_msg
.endmacro


; ============================================================================
; Complete branch macro test procedure
; ============================================================================

.proc test_branch_macro
;;;  jsr reset_screen

    LDA #$00
    STA fail_flag


    ; ========================================================================
    ; 1. UNSIGNED CONDITIONAL BRANCHES
    ; ========================================================================

    ; BEQ alias
    create_branch_test "BEQ 0 == 0 ", beq_alias, $00, $00, BRANCH_TAKEN
    create_branch_test "BEQ 0 == 1 ", beq_alias, $00, $01, BRANCH_NOT_TAKEN

    ; BNE alias
    create_branch_test "BNE 0 != 1 ", bne_alias, $00, $01, BRANCH_TAKEN
    create_branch_test "BNE 0 != 0 ", bne_alias, $00, $00, BRANCH_NOT_TAKEN

    ; Unsigned less than
    create_branch_test "BLT 0 < 1  ", blt, $00, $01, BRANCH_TAKEN
    create_branch_test "BLT 1 < 1  ", blt, $01, $01, BRANCH_NOT_TAKEN
    create_branch_test "BLT FF < 1 ", blt, $FF, $01, BRANCH_NOT_TAKEN

    ; Unsigned greater than or equal
    create_branch_test "BGE 1 >= 0 ", bge, $01, $00, BRANCH_TAKEN
    create_branch_test "BGE 1 >= 1 ", bge, $01, $01, BRANCH_TAKEN
    create_branch_test "BGE 0 >= 1 ", bge, $00, $01, BRANCH_NOT_TAKEN

    ; Unsigned greater than
    create_branch_test "BGT 2 > 1  ", bgt, $02, $01, BRANCH_TAKEN
    create_branch_test "BGT 1 > 1  ", bgt, $01, $01, BRANCH_NOT_TAKEN
    create_branch_test "BGT 0 > 1  ", bgt, $00, $01, BRANCH_NOT_TAKEN

    ; Unsigned less than or equal
    create_branch_test "BLE 0 <= 1 ", ble, $00, $01, BRANCH_TAKEN
    create_branch_test "BLE 1 <= 1 ", ble, $01, $01, BRANCH_TAKEN
    create_branch_test "BLE 2 <= 1 ", ble, $02, $01, BRANCH_NOT_TAKEN


    ; ========================================================================
    ; 2. SIGNED CONDITIONAL BRANCHES
    ; ========================================================================
    ;
    ; Signed byte values:
    ;   $00 =    0
    ;   $01 =    1
    ;   $7F =  127
    ;   $80 = -128
    ;   $FF =   -1
    ;

    ; Signed greater than or equal
    create_signed_branch_test "SBGE 0 >= 0   ", sbge, $00, $00, BRANCH_TAKEN
    create_signed_branch_test "SBGE 1 >= -1  ", sbge, $01, $FF, BRANCH_TAKEN
    create_signed_branch_test "SBGE -1 >= 1  ", sbge, $FF, $01, BRANCH_NOT_TAKEN
    create_signed_branch_test "SBGE 127>=-128", sbge, $7F, $80, BRANCH_TAKEN
    create_signed_branch_test "SBGE -128>=127", sbge, $80, $7F, BRANCH_NOT_TAKEN

    ; Signed less than
    create_signed_branch_test "SBLT -1 < 0   ", sblt, $FF, $00, BRANCH_TAKEN
    create_signed_branch_test "SBLT 0 < -1   ", sblt, $00, $FF, BRANCH_NOT_TAKEN
    create_signed_branch_test "SBLT 0 < 0    ", sblt, $00, $00, BRANCH_NOT_TAKEN
    create_signed_branch_test "SBLT -128<127 ", sblt, $80, $7F, BRANCH_TAKEN
    create_signed_branch_test "SBLT 127<-128 ", sblt, $7F, $80, BRANCH_NOT_TAKEN

    ; Signed less than or equal
    create_signed_branch_test "SBLE -1 <= 0  ", sble, $FF, $00, BRANCH_TAKEN
    create_signed_branch_test "SBLE 0 <= 0   ", sble, $00, $00, BRANCH_TAKEN
    create_signed_branch_test "SBLE 1 <= 0   ", sble, $01, $00, BRANCH_NOT_TAKEN

    ; Overflow-sensitive boundary cases
    create_signed_branch_test "SBLE -128<=127", sble, $80, $7F, BRANCH_TAKEN
    create_signed_branch_test "SBLE 127<=-128", sble, $7F, $80, BRANCH_NOT_TAKEN

    ; Additional negative/positive ordering
    create_signed_branch_test "SBLE 0 <= -1  ", sble, $00, $FF, BRANCH_NOT_TAKEN
    create_signed_branch_test "SBLE -1 <= -1 ", sble, $FF, $FF, BRANCH_TAKEN

    ; ========================================================================
    ; 3. COMBINED COMPARE-AND-BRANCH MACROS
    ; ========================================================================

    ; A == immediate
    create_a_compare_test "IF A EQ 0,0 ", if_a_eq, $00, $00, BRANCH_TAKEN
    create_a_compare_test "IF A EQ 0,1 ", if_a_eq, $00, $01, BRANCH_NOT_TAKEN

    ; A != immediate
    create_a_compare_test "IF A NE 0,1 ", if_a_ne, $00, $01, BRANCH_TAKEN
    create_a_compare_test "IF A NE 0,0 ", if_a_ne, $00, $00, BRANCH_NOT_TAKEN

    ; A < immediate, unsigned
    create_a_compare_test "IF A LT 0,1 ", if_a_lt, $00, $01, BRANCH_TAKEN
    create_a_compare_test "IF A LT 1,1 ", if_a_lt, $01, $01, BRANCH_NOT_TAKEN
    create_a_compare_test "IF A LT FF,1", if_a_lt, $FF, $01, BRANCH_NOT_TAKEN

    ; A >= immediate, unsigned
    create_a_compare_test "IF A GE 1,0 ", if_a_ge, $01, $00, BRANCH_TAKEN
    create_a_compare_test "IF A GE 1,1 ", if_a_ge, $01, $01, BRANCH_TAKEN
    create_a_compare_test "IF A GE 0,1 ", if_a_ge, $00, $01, BRANCH_NOT_TAKEN

    ; A > immediate, unsigned
    create_a_compare_test "IF A GT 2,1 ", if_a_gt, $02, $01, BRANCH_TAKEN
    create_a_compare_test "IF A GT 1,1 ", if_a_gt, $01, $01, BRANCH_NOT_TAKEN
    create_a_compare_test "IF A GT 0,1 ", if_a_gt, $00, $01, BRANCH_NOT_TAKEN

    ; A <= immediate, unsigned
    create_a_compare_test "IF A LE 0,1 ", if_a_le, $00, $01, BRANCH_TAKEN
    create_a_compare_test "IF A LE 1,1 ", if_a_le, $01, $01, BRANCH_TAKEN
    create_a_compare_test "IF A LE 2,1 ", if_a_le, $02, $01, BRANCH_NOT_TAKEN


    ; ========================================================================
    ; 4. SMART LONG-JUMP MACROS
    ; ========================================================================

    ; JEQ
    create_long_branch_test "JEQ 1 == 1 ", jeq, $01, $01, BRANCH_TAKEN
    create_long_branch_test "JEQ 1 == 2 ", jeq, $01, $02, BRANCH_NOT_TAKEN

    ; JNE
    create_long_branch_test "JNE 1 != 2 ", jne, $01, $02, BRANCH_TAKEN
    create_long_branch_test "JNE 1 != 1 ", jne, $01, $01, BRANCH_NOT_TAKEN

    ; JLT, unsigned
    create_long_branch_test "JLT 0 < 1  ", jlt, $00, $01, BRANCH_TAKEN
    create_long_branch_test "JLT 1 < 0  ", jlt, $01, $00, BRANCH_NOT_TAKEN

    ; JGE, unsigned
    create_long_branch_test "JGE 1 >= 1 ", jge, $01, $01, BRANCH_TAKEN
    create_long_branch_test "JGE 0 >= 1 ", jge, $00, $01, BRANCH_NOT_TAKEN


    ; Return with:
    ;   fail_flag = 0 if every test passed
    ;   fail_flag = 1 if one or more tests failed
    RTS
.endproc

.proc freeze_it
freeze: JMP freeze
.endproc
