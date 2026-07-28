
.proc SET_CURSOR_MATH
; -----------------------------------------------------------
; Calculate:
;
;     offset = CURSY * SCREEN_COLS + CURSX
;
; Multiplication result:
;     A         = high byte
;     COLOR_PTR = low byte
; -----------------------------------------------------------

    LDA CURSY
    STA TMP_PTR

    LDA #$00
    STA COLOR_PTR                       ; Product low byte must start at zero

    LDX #8                              ; Eight bits in CURSY

@multiply:
    LSR TMP_PTR                         ; Move next multiplier bit into carry
    BCC @shift_product

    CLC
    ADC #SCREEN_COLS                    ; Add multiplicand to partial product

@shift_product:
    ROR A                               ; Shift high product byte
    ROR COLOR_PTR                       ; Shift low product byte

    DEX
    BNE @multiply

    STA COLOR_PTR + 1                   ; Save product high byte

    ; Add column coordinate
    add16_8 COLOR_PTR, COLOR_PTR, CURSX

    ; Both pointers initially contain the screen offset
    mov16 CHAR_PTR, COLOR_PTR

    ; Add the respective base addresses
    add16i CHAR_PTR, CHAR_PTR, START_REGION_CHAR_RAM
    add16i COLOR_PTR, COLOR_PTR, START_REGION_COLOR_RAM

    RTS
.endproc
