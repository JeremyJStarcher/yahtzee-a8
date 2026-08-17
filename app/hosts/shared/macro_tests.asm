.include "shared/branch_tests.asm"
.include "shared/math_tests.asm"


; ----------------------------------------------------------------------------
; ZEROPAGE -- single allocations for the test macro test suite.
; ----------------------------------------------------------------------------

.segment "ZEROPAGE"

fail_flag:           .res 1   ; test suite failure latch
branch_test_actual:  .res 1   ; long-jump macro scratch
math_test_dest:      .res 2   ; math suite scratch word
math_test_op1:       .res 2   ; math suite scratch word
math_test_op2:       .res 2   ; math suite scratch word
math_test_val8:      .res 1   ; math suite scratch byte
