; Simple 6502 BIOS/Kernel Assembly Source
; Target: ca65 assembler from cc65 toolchain

    .include "branches.inc"
    .include "math.inc"
    .include "hw_limits.inc"
    .include "timer.mac"

    .export _irq_handler
    .export _reset_handler
    .export _nmi_handler
    .export JTCLS
    .exportzp CURS_COL
    .exportzp CURS_ROW

    .segment "CODE"

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

.macro push_ptr P
    LDA P
    PHA
    LDA P + 1
    PHA
.endmacro

.macro pop_ptr P
    PLA
    STA P + 1
    PLA
    STA P
.endmacro

.macro pushall
    PHP                                 ; Push status register
    STA SAVEA                           ; Save the 'A' register while storing the others
    PHA                                 ; Push A
    TXA                                 ; X -> A
    PHA                                 ; Push X value in A
    TYA                                 ; Y -> A
    PHA                                 ; PUSH Y value in A
    LDA SAVEA                           ; And get our original 'A' back
.endmacro

.macro popall
    PLA                                 ; Get the pushed Y value
    TAY                                 ; Transfer to Y
    PLA                                 ; Get the pushed X value
    TAX                                 ; Transfer to X
    PLA                                 ; And then get A
    PLP                                 ; Pull status register
.endmacro

.segment "ZEROPAGE"
TMP_PTR: .res 2
DISPLAY_PTR: .res 2
FILCHAR: .res 1
SAVEA: .res 1

; Cursor X position
CURS_COL: .res 1
; Cursor Y position
CURS_ROW: .res 1
; Current color
CURRENT_COLOR: .res 1
; CHAR ram ptr
CHAR_PTR: .res 2
; COLOR ram ptr
COLOR_PTR: .res 2

    .segment "CODE"

.proc DUMMY_ROUTINE
    RTS
.endproc

; ============================================================================
; Routine: DISPLAY_PSTRING
; Description:
;   Displays a Pascal-style string (length byte followed by character payload).
;   Advances CURS_COL and CURS_ROW automatically per character.
;
; Inputs:
;   DISPLAY_PTR (2 bytes, Zero Page) - Pointer to the start of the PSTRING (length byte)
;
; Registers Modified:
;   A, X, Y
; ============================================================================
.proc DISPLAY_PSTRING
    LDY #$00
    LDA (DISPLAY_PTR), Y                ; Read 1-byte string length
    TAX                                 ; Store length in X
    BEQ @done                           ; Early exit if length is 0

@loop:
    INY                                 ; Advance offset to the next character (starts at index 1)
    LDA (DISPLAY_PTR), Y                ; Fetch character

    pushall
    LDX #$00                            ; Display mode processed special chars.
    JSR DISPLAY_CHAR                    ; Draw character & advance cursor
    popall

    DEX                                 ; Decrement remaining byte count
    BNE @loop                           ; Continue until X reaches 0

@done:
    RTS
.endproc


; ASCII/control character values
CHAR_BEL = $07
CHAR_BS  = $08
CHAR_TAB = $09
CHAR_LF  = $0A
CHAR_FF  = $0C
CHAR_CR  = $0D
CHAR_DEL = $7F

; ============================================================================
; Routine: DISPLAY_CHAR
; Description:
;   Plots a single character to the screen at position (CURS_COL, CURS_ROW), updates
;   the corresponding tile in color RAM with CURRENT_COLOR, and advances
;   the cursor (wrapping to the next row if X reaches column 40).
;
; Inputs:
;   A                - Character code to write to screen
;   X                - 0 = Handle special characters (NL, etc).
;                    - 1 = raw
;   CURS_COL         - Screen X coordinate
;   CURS_ROW         - Screen Y coordinate
;   CURRENT_COLOR - Color code to write to Color RAM
; ============================================================================
.proc DISPLAY_CHAR

; Raw mode bypasses all control-character interpretation.
    CPX #$00
    BNE @draw_character

    CMP #CHAR_BEL
    BEQ @bell

    CMP #CHAR_LF
    BEQ @newline

    CMP #CHAR_CR
    BEQ @carriage_return

    CMP #CHAR_BS
    BEQ @backspace

    CMP #CHAR_TAB
    BEQ @tab

    CMP #CHAR_FF
    BEQ @form_feed

    ; Ignore unsupported C0 control characters in processed mode.
    CMP #$20
    BCC @done

    ; Optionally treat DEL as non-printing.
    CMP #CHAR_DEL
    BEQ @done

    ; --------------------------------------------------------------------
    ; Printable character path
    ; --------------------------------------------------------------------
@draw_character:
    PHA                                 ; Save character

    ; 1. Check if we need to scroll/wrap BEFORE drawing the character
    LDA CURS_COL
    CMP #SCREEN_COLS
    BCC @ready_to_draw

    ; If CURS_COL >= SCREEN_COLS, wrap line before printing this character
    JSR DISPLAY_NEXT_LINE

@ready_to_draw:
; 2. Calculate cursor location and draw character
    JSR SET_CURSOR

    LDY #$00
    PLA

    ; We not have the *print* character we want, look up the
    ; *screen code*

    TAX                                 ; Transfer to X
    LDA p2slookup, X                    ; Lookup the new screen code

    STA (CHAR_PTR), Y
    LDA CURRENT_COLOR
    STA (COLOR_PTR), Y

    ; 3. Advance cursor X position
    INC CURS_COL
@done:
    RTS

    ; --------------------------------------------------------------------
    ; Control-character handlers
    ; --------------------------------------------------------------------

@bell:
;JSR RING_BELL               ; Hardware-specific routine
    RTS                                 ; Cursor and pending wrap unchanged

@newline:
    JSR DISPLAY_NEXT_LINE               ; CR+LF semantics in this implementation
    RTS

@carriage_return:
    LDA #$00
    STA CURS_COL
    RTS

@backspace:
    LDA CURS_COL
    BEQ @done
    DEC CURS_COL
    RTS

@tab:
; Advance to the next 8-column tab stop.
; This may leave CURS_COL == SCREEN_COLS, creating pending wrap.
    LDA CURS_COL
    CLC
    ADC #8
    AND #$F8
    STA CURS_COL

    ; Clamp malformed values beyond the right edge.
    CMP #SCREEN_COLS
    BCC @done
    LDA #SCREEN_COLS
    STA CURS_COL
    RTS

@form_feed:
    JSR CLEAR_SCREEN
    RTS
.endproc

; ============================================================================
; Routine: DISPLAY_NEXT_LINE
; Description:
;   Resets CURS_COL to 0 and advances CURS_ROW to the next line.
; ============================================================================
.proc DISPLAY_NEXT_LINE
    pushall
    LDA #$00
    STA CURS_COL                        ; Reset X to left margin

    INC CURS_ROW                        ; Move down one line
    LDA CURS_ROW
    CMP #SCREEN_ROWS
    BCC @noscroll                       ; CURS_ROW < SCREEN_ROWS
    JSR SCROLL_UP
@noscroll:
    popall
    RTS
.endproc

; ============================================================================
; Compile-Time Calculated Constants for Scrolling
; ============================================================================
; Copy rows 1..23 into rows 0..22.
; The final row is cleared separately.
TOTAL_SCROLL_BYTES = (SCREEN_ROWS - 1) * SCREEN_COLS
PAGES_TO_COPY = TOTAL_SCROLL_BYTES >> 8
REM_BYTES_TO_COPY = TOTAL_SCROLL_BYTES & $FF
BOTTOM_ROW_OFFSET = (SCREEN_ROWS - 1) * SCREEN_COLS

; ============================================================================
; Routine: SCROLL_UP
; Description:
;   Shifts screen RAM (Char & Color) up by 1 row.
;   Clears the bottom row and clamps CURS_ROW to SCREEN_ROWS - 1.
; ============================================================================
.proc SCROLL_UP
    pushall
    push_ptr DISPLAY_PTR
    push_ptr TMP_PTR

    ; --------------------------------------------------------------------
    ; Step 1: Scroll Character RAM
    ; --------------------------------------------------------------------
    load16 DISPLAY_PTR, (START_REGION_CHAR_RAM + SCREEN_COLS)
    load16 TMP_PTR, START_REGION_CHAR_RAM

    JSR copy_vram_block

    ; --------------------------------------------------------------------
    ; Step 2: Scroll Color RAM
    ; --------------------------------------------------------------------
    load16 DISPLAY_PTR, (START_REGION_COLOR_RAM + SCREEN_COLS)
    load16 TMP_PTR, START_REGION_COLOR_RAM

    JSR copy_vram_block

    ; --------------------------------------------------------------------
    ; Step 3: Clear Bottom Row
    ; --------------------------------------------------------------------
    LDY #(SCREEN_COLS - 1)
@clear_bottom:

    LDA #DEFAULT_SCREEN_CHAR
    STA START_REGION_CHAR_RAM + BOTTOM_ROW_OFFSET, Y
    LDA CURRENT_COLOR
    STA START_REGION_COLOR_RAM + BOTTOM_ROW_OFFSET, Y
    DEY

    BPL @clear_bottom

    ; Clamp cursor to bottom row
    LDA #(SCREEN_ROWS - 1)
    STA CURS_ROW

    pop_ptr TMP_PTR
    pop_ptr DISPLAY_PTR
    popall
    RTS
.endproc

; ----------------------------------------------------------------------------
; Internal Helper: Copies TOTAL_SCROLL_BYTES from DISPLAY_PTR to TMP_PTR
; ----------------------------------------------------------------------------
.proc copy_vram_block
; --- Copy Full 256-byte Pages ---
    LDX #PAGES_TO_COPY
    BEQ @remaining

    LDY #$00
@page_loop:
    LDA (DISPLAY_PTR), Y
    STA (TMP_PTR), Y
    INY
    BNE @page_loop

    INC DISPLAY_PTR + 1
    INC TMP_PTR + 1
    DEX
    BNE @page_loop

    ; Copy remaining
@remaining:
    LDY #$00
    CPY #REM_BYTES_TO_COPY
    BEQ @done

@rem_loop:
    LDA (DISPLAY_PTR), Y
    STA (TMP_PTR), Y
    INY
    CPY #REM_BYTES_TO_COPY
    BNE @rem_loop

@done:
    RTS
.endproc

; Routine: SET_CURSOR
; Description:
;   Calculates the Character RAM and Color RAM addresses corresponding
;   to the current CURS_COL and CURS_ROW coordinates.
;
; Outputs:
;   CHAR_PTR  - Address in Character RAM
;   COLOR_PTR - Corresponding address in Color RAM
;
; Clobbers:
;   A, flags, TMP_PTR, CHAR_PTR, COLOR_PTR



;.segment "RODATA"
row_offsets_low:
    .repeat SCREEN_ROWS, i
    .byte <(START_REGION_CHAR_RAM + (i * SCREEN_COLS))
    .endrepeat
row_offsets_high:
    .repeat SCREEN_ROWS, i
    .byte >(START_REGION_CHAR_RAM + (i * SCREEN_COLS))
    .endrepeat

.segment "CODE"
.proc SET_CURSOR
    LDY CURS_ROW
    LDA row_offsets_low, Y
    STA CHAR_PTR
    LDA row_offsets_high, Y
    STA CHAR_PTR+1
    ; add column
    CLC
    LDA CHAR_PTR
    ADC CURS_COL
    STA CHAR_PTR
    BCC @nocarry
    INC CHAR_PTR+1
@nocarry:

    add16i COLOR_PTR, CHAR_PTR, (START_REGION_COLOR_RAM - START_REGION_CHAR_RAM)
    RTS
.endproc



.proc SET_CURSOR_MATH
; -----------------------------------------------------------
; Calculate:
;
;     offset = CURS_ROW * SCREEN_COLS + CURS_COL
;
; Multiplication result:
;     A         = high byte
;     COLOR_PTR = low byte
; -----------------------------------------------------------

    LDA CURS_ROW
    STA TMP_PTR

    LDA #$00
    STA COLOR_PTR                       ; Product low byte must start at zero

    LDX #8                              ; Eight bits in CURS_ROW

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
    add16_8 COLOR_PTR, COLOR_PTR, CURS_COL

    ; Both pointers initially contain the screen offset
    mov16 CHAR_PTR, COLOR_PTR

    ; Add the respective base addresses
    add16i CHAR_PTR, CHAR_PTR, START_REGION_CHAR_RAM
    add16i COLOR_PTR, COLOR_PTR, START_REGION_COLOR_RAM

    RTS
.endproc


.proc SET_CURSOR_FIXED_40

;; -------------------------------------------------------------------
;; Step 1: Calculate Row Offset = (CURS_ROW * 40)
;;
;; Since the 6502 lacks a hardware multiply instruction, we decompose
;; 40 into powers of two: 40 = 32 + 8 = (Y * 32) + (Y * 8).
;; We calculate (Y * 8) first via 3 bitwise left shifts (ASL/ROL).
;; -------------------------------------------------------------------
    LDA CURS_ROW
    STA CHAR_PTR                        ; Initialize low byte accumulator
    LDA #$00
    STA CHAR_PTR + 1                    ; Initialize high byte accumulator

    asl16 CHAR_PTR
    asl16 CHAR_PTR
    asl16 CHAR_PTR

    ;; Save intermediate result (CURS_ROW * 8) into temporary zero-page storage
    mov16 TMP_PTR, CHAR_PTR

    ;; Shift two more times: (CURS_ROW * 8) * 4 = (CURS_ROW * 32)
    asl16 CHAR_PTR
    asl16 CHAR_PTR

    ;; Add (CURS_ROW * 8) to (CURS_ROW * 32) to yield (CURS_ROW * 40)
    add16 CHAR_PTR, CHAR_PTR, TMP_PTR

    ;; -------------------------------------------------------------------
    ;; Step 2: Add Column Offset (CURS_COL)
    ;; -------------------------------------------------------------------
    add16_8 CHAR_PTR, CHAR_PTR, CURS_COL

    ;; -------------------------------------------------------------------
    ;; Step 3: Compute Base Pointers
    ;;
    ;; 3a. Add START_REGION_CHAR_RAM ($E000) to complete CHAR_PTR
    ;; -------------------------------------------------------------------
    add16i CHAR_PTR, CHAR_PTR, START_REGION_CHAR_RAM

    ;; 3b. Derive COLOR_PTR from CHAR_PTR
    add16i COLOR_PTR, CHAR_PTR, (START_REGION_COLOR_RAM - START_REGION_CHAR_RAM)
    RTS
.endproc


.proc CLEAR_SCREEN
    pushall
    push_ptr TMP_PTR
    push_ptr DISPLAY_PTR

    load16 TMP_PTR, START_REGION_CHAR_RAM
    load16 DISPLAY_PTR, END_REGION_CHAR_RAM

    LDA #DEFAULT_SCREEN_CHAR            ; Fill value
    JSR MEMFILL_FAST

    load16 TMP_PTR, START_REGION_COLOR_RAM
    load16 DISPLAY_PTR, END_REGION_COLOR_RAM

    LDA CURRENT_COLOR
    JSR MEMFILL_FAST

    LDX #$00
    STX CURS_COL
    STX CURS_ROW

    pop_ptr DISPLAY_PTR
    pop_ptr TMP_PTR
    popall

    RTS
.endproc


;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; Input:
;   TMP_PTR   = first address to fill
;   DISPLAY_PTR = exclusive end address
;   A         = fill byte
;
; Requires:
;   TMP_PTR <= DISPLAY_PTR
;
; Clobbers:
;   A, X, Y, TMP_PTR

.proc MEMFILL_FAST
    TAX                                 ; X = fill byte

    ; --------------------------------------------------------------------
    ; Phase 1: Clear partial start page up to the $xx00 boundary
    ; --------------------------------------------------------------------
    LDY #$00
@ALIGN_LOOP:
    LDA TMP_PTR                         ; Check if low byte is $00 (page aligned)
    BEQ @FILL_PAGES                     ; If TMP_PTR points to $xx00, head alignment is done!

    ; Check if TMP_PTR has already hit DISPLAY_PTR before we finish aligning
    CMP DISPLAY_PTR
    BNE @ALIGN_WRITE
    LDA TMP_PTR+1
    CMP DISPLAY_PTR+1
    BEQ @DONE                           ; Reached DISPLAY_PTR during alignment phase!

@ALIGN_WRITE:
    TXA
    STA (TMP_PTR), Y
    INC TMP_PTR
    BNE @ALIGN_LOOP
    INC TMP_PTR+1

    ; --------------------------------------------------------------------
    ; Phase 2: Clear whole 256-byte pages
    ; --------------------------------------------------------------------
@FILL_PAGES:
    LDA TMP_PTR+1
    CMP DISPLAY_PTR+1
    BEQ @FILL_REMAINDER                 ; High bytes match -> only partial tail page left!

    TXA
@PAGE_LOOP:
    STA (TMP_PTR), Y                    ; Write byte at (TMP_PTR) + Y
    INY                                 ; 8-bit increment (very fast!)
    BNE @PAGE_LOOP                      ; Loops 256 times until Y wraps back to $00

    INC TMP_PTR+1                       ; Advance to next 256-byte page
    JMP @FILL_PAGES

    ; --------------------------------------------------------------------
    ; Phase 3: Clear the remaining partial page
    ; --------------------------------------------------------------------
@FILL_REMAINDER:
; Y is currently $00. We fill from $00 up to DISPLAY_PTR low byte.
    TXA
@TAIL_LOOP:
    CPY DISPLAY_PTR                     ; Reached remaining byte count?
    BEQ @DONE
    STA (TMP_PTR), Y                    ; Write remaining bytes
    INY
    JMP @TAIL_LOOP

@DONE:
    RTS
.endproc

.proc reset_screen
    LDA #DEFAULT_COLOR                  ; Fill value
    STA CURRENT_COLOR
    JSR CLEAR_SCREEN
    RTS
.endproc

.proc medium_pause
; ignore-next-line
    pause_ms 2000
    RTS
.endproc

; ============================================================================
; Reset Handler
; ============================================================================
_reset_handler:
    SEI                                 ; Disable interrupts
    LDX #$FF
    TXS                                 ; Reset stack pointer to $01FF
    CLD                                 ; Clear decimal flag
    CLI                                 ; Interrupts!

    JSR reset_screen
    JSR video_test


    LDA #DEFAULT_COLOR                  ; Fill value
    STA CURRENT_COLOR
    load16 DISPLAY_PTR, boot_msg
    JSR DISPLAY_PSTRING
halt:
    JMP halt                            ; Safely trap CPU here when done

boot_msg:
    pstring2 {CHAR_FF, "Welcome to the Fantasy 6502 Console!", CHAR_BEL, CHAR_LF, "IN BUSY LOOP"}
    ;pstring2 {"Welcome to the Fantasy 6502 Console!"}

msg_welcome:
    pstring2 {$C8, "SCROLLING TEST"}

.proc video_test

; Set pointer in Zero Page
    load16 DISPLAY_PTR, msg_welcome

    LDX #100
@ploop2:
    pushall
    JSR DISPLAY_PSTRING
    popall
    DEX
    BNE @ploop2

    LDX #$00
    STX CURS_COL
    STX CURS_ROW

    LDA #$0C
    STA CURRENT_COLOR

    LDX #$00
    STX CURS_COL
    LDX #$01
    STX CURS_ROW

.repeat ::SCREEN_ROWS, I
.scope

    JMP     @print

@lstr:
    pstring .sprintf("LINE # %d", I + 1)

@print:
    pushall
    load16  DISPLAY_PTR, @lstr
    JSR     DISPLAY_PSTRING

    .if I <> ::SCREEN_ROWS-1
    JSR     DISPLAY_NEXT_LINE
    .endif

    popall

.endscope
.endrep

; lets do a run over all possible characters, just for fun.
    LDA #$C1
    STA CURRENT_COLOR

    LDX #$00
    STX CURS_COL
    LDX #$00
    STX CURS_ROW

    LDY #$00
@dl:
    pushall
    LDX #$01
    TYA
    JSR DISPLAY_CHAR
    popall
    INY                                 ; increment y
    BNE @dl                             ; didn't wrap around?

    JSR medium_pause
RTS
.endproc

; Translation table: print_code -> screen_code
; Generated from 256 font characters
;
p2slookup:
.byte $A2, $5E, $EC, $0E, $91, $48, $EA, $AC, $0A, $28, $20, $56, $F5, $81, $B9, $8D
.byte $33, $9A, $C2, $89, $A3, $A5, $F8, $AA, $6B, $05, $37, $AF, $7C, $9B, $27, $77
.byte $B5, $0F, $6E, $41, $73, $4C, $57, $A0, $19, $62, $1D, $C9, $54, $7A, $42, $22
.byte $BF, $49, $B2, $BD, $F9, $F4, $84, $FB, $C5, $A1, $26, $C3, $EF, $5B, $94, $4D
.byte $4F, $7E, $DC, $06, $23, $66, $39, $D7, $DF, $6A, $71, $8B, $6F, $9D, $60, $58
.byte $51, $88, $2B, $CF, $85, $17, $B4, $0C, $79, $F1, $4B, $D1, $0B, $DE, $F3, $18
.byte $97, $5C, $16, $63, $1E, $01, $50, $F7, $B0, $3F, $1A, $5D, $B3, $69, $95, $C0
.byte $A8, $B6, $24, $65, $F6, $1C, $52, $E3, $59, $D2, $6D, $44, $A6, $70, $75, $9C
.byte $3D, $DD, $74, $31, $8E, $7D, $BA, $86, $40, $E2, $61, $DB, $43, $00, $A9, $08
.byte $25, $8F, $ED, $A7, $E1, $93, $12, $D5, $7F, $E4, $09, $CB, $9F, $07, $D6, $3A
.byte $45, $2C, $03, $2E, $83, $C7, $AD, $FF, $E6, $BE, $C8, $FE, $9E, $C1, $35, $46
.byte $EE, $4A, $7B, $2A, $38, $CC, $1B, $CA, $5A, $8A, $67, $E7, $80, $B7, $76, $90
.byte $CD, $CE, $5F, $32, $D8, $34, $78, $11, $C6, $D9, $2F, $D4, $99, $DA, $E8, $82
.byte $D3, $02, $29, $3E, $BB, $13, $21, $E5, $0D, $1F, $55, $E0, $D0, $F2, $F0, $FC
.byte $04, $47, $36, $3C, $72, $64, $E9, $15, $FA, $2D, $68, $92, $B1, $C4, $10, $BC
.byte $AE, $6C, $53, $A4, $AB, $FD, $B8, $14, $30, $96, $87, $98, $8C, $4E, $EB, $3B


; ============================================================================
; Interrupt Handlers
; ============================================================================
_nmi_handler:
    RTI

_irq_handler:
    RTI

    ; Fixed entry points just before the vector table.
    ; These addresses are anchored by the JUMPTABLE segment in bios.cfg.
    .segment "JUMPTABLE"
    .export JTCLS
    .export JTDUMMY

JTDUMMY:
    JMP DUMMY_ROUTINE

    .segment "JUMPTABLE"
JTCLS: JMP CLEAR_SCREEN
