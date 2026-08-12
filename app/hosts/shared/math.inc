; ============================================================================
; 16-BIT SYNTHETIC MACRO SUITE FOR CA65
; ============================================================================

;; ---------------------------------------------------------------------------
; Load a 16-bit word into a pointer
; Usage: INC16 dest, immediate value
;; ---------------------------------------------------------------------------
.macro load16 PTR, IMM
    LDA #<IMM
    STA PTR
    LDA #>IMM
    STA PTR + 1
.endmacro

;; ---------------------------------------------------------------------------
; Increment 16-bit word at memory location
; Usage: INC16 ptr
;; ---------------------------------------------------------------------------
.macro inc16 ptr
    .local @skip
    INC ptr
    BNE @skip
    INC ptr + 1
@skip:
.endmacro

;; ---------------------------------------------------------------------------
; Decrement 16-bit word at memory location
; Usage: DEC16 ptr
;; ---------------------------------------------------------------------------
.macro dec16 ptr
    .local @skip
    LDA ptr
    BNE @skip
    DEC ptr + 1
@skip:
    DEC ptr
.endmacro

;; ---------------------------------------------------------------------------
; 16-Bit Addition: dest = op1 + op2 (op2 can be an immediate #val or memory addr)
; Usage: ADD16 dest, op1, op2
;        ADD16 ptr, ptr, #40
;        ADD16 dest, src1, src2
;; ---------------------------------------------------------------------------
.macro add16 dest, op1, op2
    CLC
    .if (.match (.left (1, {op2}), #))
    ; Immediate operand case (e.g., #$E000)
    LDA op1
    ADC #<(.right (.tcount ({op2}) - 1, {op2}))
    STA dest
    LDA op1 + 1
    ADC #>(.right (.tcount ({op2}) - 1, {op2}))
    STA dest + 1
    .else
    ; Memory operand case
    LDA op1
    ADC op2
    STA dest
    LDA op1 + 1
    ADC op2 + 1
    STA dest + 1
    .endif
.endmacro


;; ---------------------------------------------------------------------------
; 16-Bit Addition with Immediate/Constant Value
; Usage: ADD16I dest, op1, START_REGION_CHAR_RAM
;        ADD16I CHAR_PTR, CHAR_PTR, 40
;; ---------------------------------------------------------------------------
.macro add16i dest, op1, val
    CLC
    LDA op1
    ADC #<(val)
    STA dest
    LDA op1 + 1
    ADC #>(val)
    STA dest + 1
.endmacro


;; ---------------------------------------------------------------------------
; 16  / 8 Bit Addition with Immediate/Constant Value
; Usage: ADD16_8 (16 bit)dest, (16 bit)op1, (8 bit)op2
;; ---------------------------------------------------------------------------
.macro add16_8 dest, op1, val8
    CLC
    LDA op1
    ADC val8
    STA dest
    LDA op1 + 1
    ADC #$00
    STA dest + 1
.endmacro

;; ---------------------------------------------------------------------------
; 16-Bit Subtraction: dest = op1 - op2
; Usage: SUB16 dest, op1, op2
;; ---------------------------------------------------------------------------
.macro sub16 dest, op1, op2
    SEC
    .if (.match (.left (1, {op2}), #))
    LDA op1
    SBC #<(.right (.tcount ({op2}) - 1, {op2}))
    STA dest
    LDA op1 + 1
    SBC #>(.right (.tcount ({op2}) - 1, {op2}))
    STA dest + 1
    .else
    LDA op1
    SBC op2
    STA dest
    LDA op1 + 1
    SBC op2 + 1
    STA dest + 1
    .endif
.endmacro

.macro sub16i dest, op1, val
    SEC
    LDA op1
    SBC #<(val)
    STA dest
    LDA op1 + 1
    SBC #>(val)
    STA dest + 1
.endmacro

;; ---------------------------------------------------------------------------
; Shift Left 16-bit word (dest = dest << 1)
; Usage: ASL16 ptr
;; ---------------------------------------------------------------------------
.macro asl16 ptr
    ASL ptr
    ROL ptr + 1
.endmacro

;; ---------------------------------------------------------------------------
; Copy 16-bit word: dest = src
; Usage: MOV16 dest, src
;; ---------------------------------------------------------------------------
.macro mov16 dest, src
    .if (.match (.left (1, {src}), #))
    LDA #<(.right (.tcount ({src}) - 1, {src}))
    STA dest
    LDA #>(.right (.tcount ({src}) - 1, {src}))
    STA dest + 1
    .else
    LDA src
    STA dest
    LDA src + 1
    STA dest + 1
    .endif
.endmacro