; ============================================================================
; Math Macro Test Suite
; ============================================================================
;
; Tests the 16-bit synthetic macros in math.inc.
;
; Expected environment (matching branch_tests.asm):
;   - math.inc has already been included
;   - pstring / pstring2 are available
;   - JTSTROUT is available
;
; The tests cover:
;   - ordinary values
;   - low-byte carry / borrow propagation
;   - 16-bit wraparound
;   - immediate and memory operand forms
;   - expression immediates (#(expr)) through the .left/.right token path
;   - constant-expression values via ADD16I / SUB16I
;   - second-operand overlap and MOV16 in-place copy (dest == src)
;   - representative in-place operations (dest == op1)
; ============================================================================


; ----------------------------------------------------------------------------
; Test result strings
; ----------------------------------------------------------------------------

math_passed_msg:
    pstring2 {"  PASSED", CHAR_NL}

math_failed_msg:
    pstring2 {"  FAILED", CHAR_NL}


    ; NOTE: zero-page scratch (fail_flag, math_test_*) is allocated in a
    ; single consolidated ZEROPAGE section at the top level (fconsole.asm).

.segment "CODE"

; ============================================================================
; Test setup helpers
;
; These deliberately do not use the macros from math.inc.
; ============================================================================

.macro math_set16 ptr, value
    LDA #<value
    STA ptr
    LDA #>value
    STA ptr + 1
.endmacro


.macro math_set8 ptr, value
    LDA #value
    STA ptr
.endmacro


; ============================================================================
; Assertions
; ============================================================================

.macro math_assert16 ptr, expected
    .local failed
    .local done

    LDA ptr
    CMP #<expected
    BNE failed

    LDA ptr + 1
    CMP #>expected
    BEQ done

failed:
    mark_test_failed

done:
.endmacro


.macro math_assert8 ptr, expected
    .local done

    LDA ptr
    CMP #expected
    BEQ done

    mark_test_failed

done:
.endmacro


; ============================================================================
; Finish one test
;
; As in branch_tests.asm, a failure prints FAILED and freezes immediately.
; ============================================================================

.macro math_finish_test
    .local passed

    LDA fail_flag
    BEQ passed

    host_print_pstring math_failed_msg
    JMP math_freeze_it

passed:
    host_print_pstring math_passed_msg
.endmacro


; ============================================================================
; Test LOAD16
;
; Example:
;   create_load16_test "LOAD16 1234", $1234
; ============================================================================

.macro create_load16_test test_name, value
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    ; Sentinel proves both bytes are overwritten.
    math_set16 math_test_dest, $A55A

    load16 math_test_dest, value

    math_assert16 math_test_dest, value
    math_finish_test
.endmacro


; ============================================================================
; Test unary 16-bit macros:
;   INC16
;   DEC16
;   ASL16
;
; Example:
;   create_unary16_test "INC16 12FF", inc16, $12FF, $1300
; ============================================================================

.macro create_unary16_test test_name, macroopcode, initial, expected
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_dest, initial

    macroopcode math_test_dest

    math_assert16 math_test_dest, expected
    math_finish_test
.endmacro


; ============================================================================
; Test ADD16 / SUB16 with a memory operand
;
; Also verifies that op1 and op2 are not modified when dest is separate.
; ============================================================================

.macro create_binary16_mem_test test_name, macroopcode, lhs, rhs, expected
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_dest, $A55A
    math_set16 math_test_op1, lhs
    math_set16 math_test_op2, rhs

    macroopcode math_test_dest, math_test_op1, math_test_op2

    math_assert16 math_test_dest, expected
    math_assert16 math_test_op1, lhs
    math_assert16 math_test_op2, rhs
    math_finish_test
.endmacro


; ============================================================================
; Test ADD16 / SUB16 with an immediate operand (#value)
; ============================================================================

.macro create_binary16_imm_test test_name, macroopcode, lhs, rhs, expected
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_dest, $A55A
    math_set16 math_test_op1, lhs

    ; Pass the immediate token sequence through unchanged.  math.inc uses
    ; .match ({op2}, {#}) to distinguish immediate from memory operands.
    macroopcode math_test_dest, math_test_op1, rhs

    math_assert16 math_test_dest, expected
    math_assert16 math_test_op1, lhs
    math_finish_test
.endmacro


; ============================================================================
; Test ADD16 / SUB16 with an expression immediate (#(expr))
;
; This is the form that stresses the token extraction in math.inc:
;
;     #<(.right (.tcount ({op2}) - 1, {op2}))
;
; must resolve correctly when the text after '#' is a compound constant
; expression rather than a plain hex value.
; ============================================================================

.macro create_binary16_expr_imm_test test_name, macroopcode, lhs, expr, expected
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_dest, $A55A
    math_set16 math_test_op1, lhs

    macroopcode math_test_dest, math_test_op1, #(expr)

    math_assert16 math_test_dest, expected
    math_assert16 math_test_op1, lhs
    math_finish_test
.endmacro


; ============================================================================
; Test ADD16I / SUB16I
; ============================================================================

.macro create_binary16_const_test test_name, macroopcode, lhs, rhs, expected
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_dest, $A55A
    math_set16 math_test_op1, lhs

    macroopcode math_test_dest, math_test_op1, rhs

    math_assert16 math_test_dest, expected
    math_assert16 math_test_op1, lhs
    math_finish_test
.endmacro


; ============================================================================
; Test ADD16 / SUB16 in-place:
;
;       dest == op1
; ============================================================================

.macro create_binary16_inplace_mem_test test_name, macroopcode, lhs, rhs, expected
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_dest, lhs
    math_set16 math_test_op2, rhs

    macroopcode math_test_dest, math_test_dest, math_test_op2

    math_assert16 math_test_dest, expected
    math_assert16 math_test_op2, rhs
    math_finish_test
.endmacro


.macro create_binary16_inplace_imm_test test_name, macroopcode, lhs, rhs, expected
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_dest, lhs

    ; As above, rhs already includes the leading # at the call site.
    macroopcode math_test_dest, math_test_dest, rhs

    math_assert16 math_test_dest, expected
    math_finish_test
.endmacro


.macro create_binary16_inplace_const_test test_name, macroopcode, lhs, rhs, expected
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_dest, lhs

    macroopcode math_test_dest, math_test_dest, rhs

    math_assert16 math_test_dest, expected
    math_finish_test
.endmacro


; ============================================================================
; Test ADD16_8
; ============================================================================

.macro create_add16_8_test test_name, lhs, rhs8, expected
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_dest, $A55A
    math_set16 math_test_op1, lhs
    math_set8 math_test_val8, rhs8

    add16_8 math_test_dest, math_test_op1, math_test_val8

    math_assert16 math_test_dest, expected
    math_assert16 math_test_op1, lhs
    math_assert8 math_test_val8, rhs8
    math_finish_test
.endmacro


.macro create_add16_8_inplace_test test_name, lhs, rhs8, expected
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_dest, lhs
    math_set8 math_test_val8, rhs8

    add16_8 math_test_dest, math_test_dest, math_test_val8

    math_assert16 math_test_dest, expected
    math_assert8 math_test_val8, rhs8
    math_finish_test
.endmacro


; ============================================================================
; Test MOV16
; ============================================================================

.macro create_mov16_mem_test test_name, value
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_dest, $A55A
    math_set16 math_test_op1, value

    mov16 math_test_dest, math_test_op1

    math_assert16 math_test_dest, value
    math_assert16 math_test_op1, value
    math_finish_test
.endmacro


.macro create_mov16_imm_test test_name, src, expected
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_dest, $A55A

    ; src includes the leading # so MOV16 sees the exact token form it expects.
    mov16 math_test_dest, src

    math_assert16 math_test_dest, expected
    math_finish_test
.endmacro


; ============================================================================
; Test ADD16 / SUB16 where the destination overlaps the second operand:
;
;       dest == op2
;
; The memory-operand form stores the low byte of dest before reading the
; high byte of op2, so this aliasing order must still compute lhs + rhs (or
; lhs - rhs) correctly even though both names point at the same buffer.
; ============================================================================

.macro create_binary16_dest_eq_op2_test test_name, macroopcode, lhs, rhs, expected
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_op1, lhs
    math_set16 math_test_op2, rhs

    ; The destination buffer is also the second operand.
    macroopcode math_test_op2, math_test_op1, math_test_op2

    math_assert16 math_test_op2, expected
    math_assert16 math_test_op1, lhs
    math_finish_test
.endmacro


; ============================================================================
; Test MOV16 self-copy:
;
;       dest == src
;
; mov16 writes only the low byte before it reads the high byte of the source,
; so a fully-overlapping copy must be safe for every 16-bit value.
; ============================================================================

.macro create_mov16_self_copy_test test_name, value
    .local test_string
    .local test_start

    JMP test_start

test_string:
    pstring test_name

test_start:
    host_print_pstring test_string

    math_set16 math_test_op1, value

    mov16 math_test_op1, math_test_op1

    math_assert16 math_test_op1, value
    math_finish_test
.endmacro


; ============================================================================
; Complete math macro test procedure
; ============================================================================

; Symbolic constants used by the expression-immediate tests below. They exist
; to prove that compound constant expressions survive the .left/.right token
; extraction in math.inc (not just plain hex literals).
MATH_LOCAL_HI  = $02
MATH_LOCAL_LO  = $34


.proc test_math_macro

; All arithmetic tests assume normal binary arithmetic.
    CLD


    ; ========================================================================
    ; 1. LOAD16
    ; ========================================================================

    create_load16_test "LOAD16 0000        ", $0000
    create_load16_test "LOAD16 1234        ", $1234
    create_load16_test "LOAD16 FFFF        ", $FFFF


    ; ========================================================================
    ; 2. INC16
    ; ========================================================================

    ; No carry into the high byte.
    create_unary16_test "INC16 1234 -> 1235", inc16, $1234, $1235

    ; Low-byte wrap propagates into the high byte.
    create_unary16_test "INC16 12FF -> 1300", inc16, $12FF, $1300

    ; Full 16-bit wraparound.
    create_unary16_test "INC16 FFFF -> 0000", inc16, $FFFF, $0000


    ; ========================================================================
    ; 3. DEC16
    ; ========================================================================

    ; No borrow from the high byte.
    create_unary16_test "DEC16 1235 -> 1234", dec16, $1235, $1234

    ; Low-byte borrow propagates into the high byte.
    create_unary16_test "DEC16 1300 -> 12FF", dec16, $1300, $12FF

    ; Full 16-bit wraparound.
    create_unary16_test "DEC16 0000 -> FFFF", dec16, $0000, $FFFF


    ; ========================================================================
    ; 4. ADD16 - MEMORY OPERAND
    ; ========================================================================

    create_binary16_mem_test "ADD16 1234 + 0102 ", add16, $1234, $0102, $1336
    create_binary16_mem_test "ADD16 12FF + 0001 ", add16, $12FF, $0001, $1300
    create_binary16_mem_test "ADD16 FFFF + 0001 ", add16, $FFFF, $0001, $0000

    ; dest == op2: the destination buffer is also the second operand.
    create_binary16_dest_eq_op2_test "ADD16 dest==op2   ", add16, $7F80, $0040, $7FC0

    ; Representative in-place add (dest == op1).
    create_binary16_inplace_mem_test "ADD16 inplace 00FF ", add16, $00FF, $0001, $0100


    ; ========================================================================
    ; 5. ADD16 - IMMEDIATE OPERAND
    ; ========================================================================

    create_binary16_imm_test "ADD16 # 1234+00CC ", add16, $1234, #$00CC, $1300
    create_binary16_imm_test "ADD16 # F000+2000 ", add16, $F000, #$2000, $1000
    create_binary16_inplace_imm_test "ADD16 # inplace    ", add16, $00FF, #$0028, $0127

    ; Expression immediates: compound constant expressions after '#'.
    create_binary16_expr_imm_test "ADD16 #($x*256+$y)", add16, $1234, (MATH_LOCAL_HI * 256 + MATH_LOCAL_LO), $1468
    create_binary16_expr_imm_test "ADD16 #(1)       ", add16, $FFFF, (1), $0000
    create_binary16_expr_imm_test "ADD16 #($8000+$12)", add16, $0010, ($8000 + $12), $8022


    ; ========================================================================
    ; 6. ADD16I
    ; ========================================================================

    create_binary16_const_test "ADD16I 1234+0001  ", add16i, $1234, $0001, $1235
    create_binary16_const_test "ADD16I 12FF+0001  ", add16i, $12FF, $0001, $1300
    create_binary16_const_test "ADD16I FFFF+0001  ", add16i, $FFFF, $0001, $0000
    create_binary16_inplace_const_test "ADD16I inplace     ", add16i, $00FF, $0028, $0127

    ; The (4 * 6) expression folds to $18 at assembly time; the sum wraps
    ; out of 16 bits ($FFF4 + $18 = $1000C -> $000C).
    create_binary16_const_test "ADD16I (4*6)     ", add16i, $FFF4, (4 * 6), $000C


    ; ========================================================================
    ; 7. ADD16_8
    ; ========================================================================

    create_add16_8_test "ADD16_8 1234 + 22 ", $1234, $22, $1256
    create_add16_8_test "ADD16_8 12F0 + 20 ", $12F0, $20, $1310
    create_add16_8_test "ADD16_8 FFFF + 01 ", $FFFF, $01, $0000
    create_add16_8_inplace_test "ADD16_8 inplace   ", $00F0, $20, $0110


    ; ========================================================================
    ; 8. SUB16 - MEMORY OPERAND
    ; ========================================================================

    create_binary16_mem_test "SUB16 1234 - 0102 ", sub16, $1234, $0102, $1132
    create_binary16_mem_test "SUB16 1300 - 0001 ", sub16, $1300, $0001, $12FF
    create_binary16_mem_test "SUB16 0000 - 0001 ", sub16, $0000, $0001, $FFFF
    create_binary16_mem_test "SUB16 1000 - 2000 ", sub16, $1000, $2000, $F000

    ; Representative in-place subtract (dest == op1).
    create_binary16_inplace_mem_test "SUB16 inplace 0100 ", sub16, $0100, $0001, $00FF


    ; ========================================================================
    ; 9. SUB16 - IMMEDIATE OPERAND
    ; ========================================================================

    create_binary16_imm_test "SUB16 # 1234-0034 ", sub16, $1234, #$0034, $1200
    create_binary16_imm_test "SUB16 # 1000-1001 ", sub16, $1000, #$1001, $FFFF
    create_binary16_inplace_imm_test "SUB16 # inplace    ", sub16, $0100, #$0028, $00D8

    ; Expression immediates: compound constant expressions after '#'.
    create_binary16_expr_imm_test "SUB16 #($x*256+$y)", sub16, $1268, (MATH_LOCAL_HI * 256 + MATH_LOCAL_LO), $1034
    create_binary16_expr_imm_test "SUB16 #($8000+$12)", sub16, $8030, ($8000 + $12), $001E


    ; ========================================================================
    ; 10. SUB16I
    ; ========================================================================

    create_binary16_const_test "SUB16I 1234-0001  ", sub16i, $1234, $0001, $1233
    create_binary16_const_test "SUB16I 1300-0001  ", sub16i, $1300, $0001, $12FF
    create_binary16_const_test "SUB16I 0000-0001  ", sub16i, $0000, $0001, $FFFF
    create_binary16_inplace_const_test "SUB16I inplace     ", sub16i, $0100, $0028, $00D8

    ; Constant expression folded at assembly time.  Borrows through the top bit.
    create_binary16_const_test "SUB16I (4*7)      ", sub16i, $0000, (4 * 7), $FFE4


    ; ========================================================================
    ; 11. ASL16
    ; ========================================================================

    create_unary16_test "ASL16 1234 -> 2468", asl16, $1234, $2468

    ; Bit 7 of the low byte must rotate into bit 0 of the high byte.
    create_unary16_test "ASL16 0080 -> 0100", asl16, $0080, $0100

    ; Bit 15 falls off the top of the 16-bit value.
    create_unary16_test "ASL16 8000 -> 0000", asl16, $8000, $0000

    create_unary16_test "ASL16 FFFF -> FFFE", asl16, $FFFF, $FFFE


    ; ========================================================================
    ; 12. MOV16
    ; ========================================================================

    create_mov16_mem_test "MOV16 mem 0000     ", $0000
    create_mov16_mem_test "MOV16 mem 1234     ", $1234
    create_mov16_mem_test "MOV16 mem FFFF     ", $FFFF

    create_mov16_imm_test "MOV16 imm 0000     ", #$0000, $0000
    create_mov16_imm_test "MOV16 imm BEEF     ", #$BEEF, $BEEF
    create_mov16_imm_test "MOV16 imm FFFF     ", #$FFFF, $FFFF


    ; ------------------------------------------------------------------------
    ; 12a. MOV16 in-place copy (dest == src)
    ;
    ; The source high byte is read only after the destination low byte has
    ; been written, so this exercises the overlapping-buffer ordering on the
    ; middle and boundary values.
    ; ------------------------------------------------------------------------

    create_mov16_self_copy_test "MOV16 self BEEF   ", $BEEF
    create_mov16_self_copy_test "MOV16 self 0000   ", $0000
    create_mov16_self_copy_test "MOV16 self FFFF   ", $FFFF


    ; Return with:
    ;   fail_flag = 0 if every test passed
    ;   fail_flag = 1 if a test failed
    ;
    ; A failed test freezes immediately, matching branch_tests.asm.
    RTS
.endproc


.proc math_freeze_it
freeze:
    JMP freeze
.endproc
