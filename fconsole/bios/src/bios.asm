; Simple 6502 BIOS/Kernel Assembly Source
; Target: ca65 assembler from cc65 toolchain

    .include "branches.inc"
    .include "math.inc"

    .export _irq_handler
    .export _reset_handler
    .export _nmi_handler
    .export JTCLS
    .exportzp CURSX
    .exportzp CURSY

    .segment "CODE"

.macro pstring str
    .byte .strlen(str), str
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


SCREEN_COLS = 40
SCREEN_ROWS = 24
SCREEN_SIZE = SCREEN_COLS * SCREEN_ROWS

START_REGION_CHAR_RAM = $E000
END_REGION_CHAR_RAM = START_REGION_CHAR_RAM + SCREEN_SIZE

START_REGION_COLOR_RAM = $E400
END_REGION_COLOR_RAM = START_REGION_COLOR_RAM + SCREEN_SIZE

DEFAULT_COLOR = $6F
DEFAULT_SCREEN_CHAR = ' '

.segment "ZEROPAGE"
TMP_PTR: .res 2
PRINT_PTR: .res 2
FILCHAR: .res 1
SAVEA: .res 1

; Cursor X position
CURSX: .res 1
; Cursor Y position
CURSY: .res 1
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
; Routine: PRINT_PSTRING
; Description:
;   Prints a Pascal-style string (length byte followed by character payload).
;   Advances CURSX and CURSY automatically per character.
;
; Inputs:
;   PRINT_PTR (2 bytes, Zero Page) - Pointer to the start of the PSTRING (length byte)
;
; Registers Modified:
;   A, X, Y
; ============================================================================
.proc PRINT_PSTRING
    LDY #$00
    LDA (PRINT_PTR), Y                  ; Read 1-byte string length
    TAX                                 ; Store length in X
    BEQ @done                           ; Early exit if length is 0

@loop:
    INY                                 ; Advance offset to the next character (starts at index 1)
    LDA (PRINT_PTR), Y                  ; Fetch character

    pushall
    JSR DISPLAY_CHAR                    ; Draw character & advance cursor
    popall

    DEX                                 ; Decrement remaining byte count
    BNE @loop                           ; Continue until X reaches 0

@done:
    RTS
.endproc

; ============================================================================
; Routine: DISPLAY_CHAR
; Description:
;   Plots a single character to the screen at position (CURSX, CURSY), updates
;   the corresponding tile in Color RAM with CURRENT_COLOR, and advances
;   the cursor (wrapping to the next row if X reaches column 40).
;
; Inputs:
;   A             - Character code to write to screen
;   CURSX         - Screen X coordinate
;   CURSY         - Screen Y coordinate
;   CURRENT_COLOR - Color code to write to Color RAM
; ============================================================================
.proc DISPLAY_CHAR
    PHA                                 ; Save character

    ; 1. Check if we need to scroll/wrap BEFORE drawing the character
    LDA CURSX
    CMP #SCREEN_COLS
    BCC @ready_to_draw

    ; If CURSX >= 40, wrap line before printing this character
    JSR DISPLAY_NEXT_LINE

@ready_to_draw:
; 2. Calculate cursor location and draw character
    JSR SET_CURSOR

    LDY #$00
    PLA                                 ; Restore character
    STA (CHAR_PTR), Y
    LDA CURRENT_COLOR
    STA (COLOR_PTR), Y

    ; 3. Advance cursor X position
    INC CURSX
    RTS
.endproc


; ============================================================================
; Routine: DISPLAY_NEXT_LINE
; Description:
;   Resets CURSX to 0 and advances CURSY to the next line.
; ============================================================================
.proc DISPLAY_NEXT_LINE
    pushall
    LDA #$00
    STA CURSX                           ; Reset X to left margin

    INC CURSY                           ; Move down one line (0..23 -> 1..24)
    LDA CURSY
    CMP #SCREEN_ROWS
    BCC @noscroll                       ; CURSY < SCREEN_ROWS
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
;   Clears the bottom row and clamps CURSY to SCREEN_ROWS - 1.
; ============================================================================
.proc SCROLL_UP
    pushall
    push_ptr PRINT_PTR
    push_ptr TMP_PTR

    ; --------------------------------------------------------------------
    ; Step 1: Scroll Character RAM
    ; --------------------------------------------------------------------
    load16 PRINT_PTR, (START_REGION_CHAR_RAM + SCREEN_COLS)
    load16 TMP_PTR, START_REGION_CHAR_RAM

    JSR copy_vram_block

    ; --------------------------------------------------------------------
    ; Step 2: Scroll Color RAM
    ; --------------------------------------------------------------------
    load16 PRINT_PTR, (START_REGION_COLOR_RAM + SCREEN_COLS)
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
    STA CURSY

    pop_ptr TMP_PTR
    pop_ptr PRINT_PTR
    popall
    RTS
.endproc

; ----------------------------------------------------------------------------
; Internal Helper: Copies TOTAL_SCROLL_BYTES from PRINT_PTR to TMP_PTR
; ----------------------------------------------------------------------------
.proc copy_vram_block
; --- Copy Full 256-byte Pages ---
    LDX #PAGES_TO_COPY
    BEQ @remaining

    LDY #$00
@page_loop:
    LDA (PRINT_PTR), Y
    STA (TMP_PTR), Y
    INY
    BNE @page_loop

    INC PRINT_PTR + 1
    INC TMP_PTR + 1
    DEX
    BNE @page_loop

    ; Copy remaining
@remaining:
    LDY #$00
    CPY #REM_BYTES_TO_COPY
    BEQ @done

@rem_loop:
    LDA (PRINT_PTR), Y
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
;   to the current CURSX and CURSY coordinates.
;
; Outputs:
;   CHAR_PTR  - Address in Character RAM
;   COLOR_PTR - Corresponding address in Color RAM
;
; Clobbers:
;   A, flags, TMP_PTR, CHAR_PTR, COLOR_PTR

.proc SET_CURSOR
;; -------------------------------------------------------------------
;; Step 1: Calculate Row Offset = (CURSY * 40)
;;
;; Since the 6502 lacks a hardware multiply instruction, we decompose
;; 40 into powers of two: 40 = 32 + 8 = (Y * 32) + (Y * 8).
;; We calculate (Y * 8) first via 3 bitwise left shifts (ASL/ROL).
;; -------------------------------------------------------------------
    LDA CURSY
    STA CHAR_PTR                        ; Initialize low byte accumulator
    LDA #$00
    STA CHAR_PTR + 1                    ; Initialize high byte accumulator

    asl16 CHAR_PTR
    asl16 CHAR_PTR
    asl16 CHAR_PTR

    ;; Save intermediate result (CURSY * 8) into temporary zero-page storage
    mov16 TMP_PTR, CHAR_PTR

    ;; Shift two more times: (CURSY * 8) * 4 = (CURSY * 32)
    asl16 CHAR_PTR
    asl16 CHAR_PTR

    ;; Add (CURSY * 8) to (CURSY * 32) to yield (CURSY * 40)
    add16 CHAR_PTR, CHAR_PTR, TMP_PTR

    ;; -------------------------------------------------------------------
    ;; Step 2: Add Column Offset (CURSX)
    ;; -------------------------------------------------------------------
    add16_8 CHAR_PTR, CHAR_PTR, CURSX

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
    load16 TMP_PTR, START_REGION_CHAR_RAM
    load16 PRINT_PTR, END_REGION_CHAR_RAM

    LDA #DEFAULT_SCREEN_CHAR            ; Fill value
    JSR MEMFILL_FAST

    load16 TMP_PTR, START_REGION_COLOR_RAM
    load16 PRINT_PTR, END_REGION_COLOR_RAM

    LDA CURRENT_COLOR
    JSR MEMFILL_FAST

    LDX #$00
    STX CURSX
    STX CURSY

    RTS
.endproc


;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
; Input:
;   TMP_PTR   = first address to fill
;   PRINT_PTR = exclusive end address
;   A         = fill byte
;
; Requires:
;   TMP_PTR <= PRINT_PTR
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

    ; Check if TMP_PTR has already hit PRINT_PTR before we finish aligning
    CMP PRINT_PTR
    BNE @ALIGN_WRITE
    LDA TMP_PTR+1
    CMP PRINT_PTR+1
    BEQ @DONE                           ; Reached PRINT_PTR during alignment phase!

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
    CMP PRINT_PTR+1
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
; Y is currently $00. We fill from $00 up to PRINT_PTR low byte.
    TXA
@TAIL_LOOP:
    CPY PRINT_PTR                       ; Reached remaining byte count?
    BEQ @DONE
    STA (TMP_PTR), Y                    ; Write remaining bytes
    INY
    JMP @TAIL_LOOP

@DONE:
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

    LDA #DEFAULT_COLOR                  ; Fill value
    STA CURRENT_COLOR
    JSR CLEAR_SCREEN

    ; Set pointer in Zero Page
    load16 PRINT_PTR, msg_welcome

halt:
    JSR PRINT_PSTRING
    JMP halt                            ; Safely trap CPU here when done

msg_welcome:
    pstring "Welcome to the Fantasy 6502 Console!"

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
