; ============================================================================
; 16-BIT SYNTHETIC MACRO SUITE FOR CA65
; ============================================================================

;; ---------------------------------------------------------------------------
; Load a 16-bit word into a pointer
; Usage: INC16 dest, immediate value
;; ---------------------------------------------------------------------------
.macro LOAD16 PTR, IMM
        LDA #<IMM
        STA PTR
        LDA #>IMM
        STA PTR + 1
.endmacro

;; ---------------------------------------------------------------------------
; Increment 16-bit word at memory location
; Usage: INC16 ptr
;; ---------------------------------------------------------------------------
.macro INC16 ptr
    .local @skip
    inc ptr
    bne @skip
    inc ptr + 1
@skip:
.endmacro

;; ---------------------------------------------------------------------------
; Decrement 16-bit word at memory location
; Usage: DEC16 ptr
;; ---------------------------------------------------------------------------
.macro DEC16 ptr
    .local @skip
    lda ptr
    bne @skip
    dec ptr + 1
@skip:
    dec ptr
.endmacro

;; ---------------------------------------------------------------------------
; 16-Bit Addition: dest = op1 + op2 (op2 can be an immediate #val or memory addr)
; Usage: ADD16 dest, op1, op2
;        ADD16 ptr, ptr, #40
;        ADD16 dest, src1, src2
;; ---------------------------------------------------------------------------
.macro ADD16 dest, op1, op2
    clc
    .if (.match ({op2}, {#}))
        ; Immediate operand case (e.g., #$E000)
        lda op1
        adc #<(.right (1, {op2}))
        sta dest
        lda op1 + 1
        adc #>(.right (1, {op2}))
        sta dest + 1
    .else
        ; Memory operand case
        lda op1
        adc op2
        sta dest
        lda op1 + 1
        adc op2 + 1
        sta dest + 1
    .endif
.endmacro


;; ---------------------------------------------------------------------------
; 16-Bit Addition with Immediate/Constant Value
; Usage: ADD16I dest, op1, START_REGION_CHAR_RAM
;        ADD16I CHAR_PTR, CHAR_PTR, 40
;; ---------------------------------------------------------------------------
.macro ADD16I dest, op1, val
    clc
    lda op1
    adc #<(val)
    sta dest
    lda op1 + 1
    adc #>(val)
    sta dest + 1
.endmacro

;; ---------------------------------------------------------------------------
; 16-Bit Subtraction: dest = op1 - op2
; Usage: SUB16 dest, op1, op2
;; ---------------------------------------------------------------------------
.macro SUB16 dest, op1, op2
    sec
    .if (.match ({op2}, {#}))
        lda op1
        sbc #<(.right (1, {op2}))
        sta dest
        lda op1 + 1
        sbc #>(.right (1, {op2}))
        sta dest + 1
    .else
        lda op1
        sbc op2
        sta dest
        lda op1 + 1
        sbc op2 + 1
        sta dest + 1
    .endif
.endmacro

.macro SUB16I dest, op1, val
    sec
    lda op1
    sbc #<(val)
    sta dest
    lda op1 + 1
    sbc #>(val)
    sta dest + 1
.endmacro

;; ---------------------------------------------------------------------------
; Shift Left 16-bit word (dest = dest << 1)
; Usage: ASL16 ptr
;; ---------------------------------------------------------------------------
.macro ASL16 ptr
    asl ptr
    rol ptr + 1
.endmacro

;; ---------------------------------------------------------------------------
; Copy 16-bit word: dest = src
; Usage: MOV16 dest, src
;; ---------------------------------------------------------------------------
.macro MOV16 dest, src
    .if (.match ({src}, {#}))
        lda #<(.right (1, {src}))
        sta dest
        lda #>(.right (1, {src}))
        sta dest + 1
    .else
        lda src
        sta dest
        lda src + 1
        sta dest + 1
    .endif
.endmacro