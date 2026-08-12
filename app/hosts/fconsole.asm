.import __RAM_START__

; ASCII/control character values
CHAR_BEL = $07
CHAR_BS  = $08
CHAR_TAB = $09
CHAR_LF  = $0A
CHAR_FF  = $0C
CHAR_CR  = $0D
CHAR_NL  = $0A
CHAR_DEL = $7F

CHAR_ARROW_UP = $81
CHAR_ARROW_DOWN = $82
CHAR_ARROW_LEFT = $83
CHAR_ARROW_RIGHT = $84




.macro pstring str
    .byte .strlen(str), str
.endmacro


.macro pstring2 payload
    .local data_start, data_end

    ; Pascal-string length byte
    .byte data_end - data_start

data_start:
    .byte payload
data_end:

    .assert (data_end - data_start) <= $FF, error, "pstring2 payload exceeds 255 bytes"
.endmacro

JTCLS = $FF03
JTDUMMY = $FF00
JTGETKEY = $FF06
JTSTROUT = $FF09                        ;  Prints a pstring A = high byte of pointer  X = low byte of pointer



.include "shared/branches.inc"
.include "shared/branch_tests.asm"


.segment "VECTORS"
    .addr __RAM_START__                 ; load_address
    .addr start                         ; start_ptr

    .segment "CODE"

.proc start
    LDX #<boot_msg
    LDA #>boot_msg
    JSR JTSTROUT

    JSR test_branch_macro

    LDX #<end_msg
    LDA #>end_msg
    JSR JTSTROUT


ll:
    JMP ll

boot_msg:
    pstring2 {CHAR_NL, "RUNNING PROGRAM", CHAR_BEL, CHAR_NL}


end_msg:
    pstring2 {CHAR_NL, "HALTED", CHAR_BEL, CHAR_NL}

.endproc