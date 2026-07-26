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

.MACRO PUSH_PTR P
        LDA P
        PHA
        LDA P + 1
        PHA
.endmacro

.MACRO POP_PTR P
        PLA
        STA P + 1
        PLA
        STA P
.endmacro

.MACRO PUSHALL
    php           ; Push status register
    STA SAVEA     ; Save the 'A' register while storing the others
    pha           ; Push A
    txa           ; X -> A
    pha           ; Push X value in A
    tya           ; Y -> A
    pha           ; PUSH Y value in A
    LDA SAVEA     ; And get our original 'A' back
.ENDMacro

.MACRO POPALL
    PLA           ; Get the pushed Y value
    TAY           ; Transfer to Y
    PLA           ; Get the pushed X value
    TAX           ; Transfer to X
    PLA           ; And then get A
    plp           ; Pull status register
.ENDMacro


SCREEN_COLS = 40
SCREEN_ROWS = 25

START_REGION_CHAR_RAM = $E000
END_REGION_CHAR_RAM   = START_REGION_CHAR_RAM + (40 * 25)

START_REGION_COLOR_RAM = $C000
END_REGION_COLOR_RAM   = START_REGION_COLOR_RAM + (40 * 25)

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
;   TMP_PTR (2 bytes, Zero Page) - Pointer to the start of the PSTRING (length byte)
;
; Registers Modified:
;   A, X, Y
; ============================================================================
.proc PRINT_PSTRING
        LDY #$00
        LDA (PRINT_PTR),Y         ; Read 1-byte string length
        TAX                     ; Store length in X
        BEQ @done               ; Early exit if length is 0

@loop:
        INY                     ; Advance offset to the next character (starts at index 1)
        LDA (PRINT_PTR),Y         ; Fetch character

        PUSHALL
        JSR DISPLAY_CHAR        ; Draw character & advance cursor
        POPALL

        DEX                     ; Decrement remaining byte count
        BNE @loop               ; Continue until X reaches 0

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
;   CURSX         - Screen X coordinate (0 - 39)
;   CURSY         - Screen Y coordinate (0 - 24)
;   CURRENT_COLOR - Color code to write to Color RAM
; ============================================================================
.proc DISPLAY_CHAR
        PHA                     ; Save character

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
        PLA                     ; Restore character
        STA (CHAR_PTR),Y
        LDA CURRENT_COLOR
        STA (COLOR_PTR),Y

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
        PUSHALL
        LDA #$00
        STA CURSX               ; Reset X to left margin

        INC CURSY               ; Move down one line (0..23 -> 1..24)
        LDA CURSY
        CMP #SCREEN_ROWS -1
        BNE @noscroll
        JSR SCROLL_UP
        DEC CURSY
@noscroll:
        POPALL
        RTS
.endproc

; ============================================================================
; Compile-Time Calculated Constants for Scrolling
; ============================================================================
TOTAL_SCROLL_BYTES = (SCREEN_ROWS - 1) * SCREEN_COLS  ; 24 * 40 = 960 ($03C0)
PAGES_TO_COPY      = TOTAL_SCROLL_BYTES >> 8           ; 960 / 256 = 3 full pages
REM_BYTES_TO_COPY  = TOTAL_SCROLL_BYTES & $FF          ; 960 % 256 = 192 bytes ($C0)
BOTTOM_ROW_OFFSET  = ((SCREEN_ROWS - 2) * SCREEN_COLS)  ; Start of row 24 (960 / $03C0)

; ============================================================================
; Routine: SCROLL_UP
; Description:
;   Shifts screen RAM (Char & Color) up by 1 row.
;   Clears the bottom row and clamps CURSY to SCREEN_ROWS - 1.
; ============================================================================
.proc SCROLL_UP
        PUSHALL
        PUSH_PTR PRINT_PTR
        PUSH_PTR TMP_PTR

        ; --------------------------------------------------------------------
        ; Step 1: Scroll Character RAM
        ; --------------------------------------------------------------------
        LOAD16 PRINT_PTR, (START_REGION_CHAR_RAM + SCREEN_COLS)
        LOAD16 TMP_PTR, START_REGION_CHAR_RAM

        JSR copy_vram_block

        ; --------------------------------------------------------------------
        ; Step 2: Scroll Color RAM
        ; --------------------------------------------------------------------
        LOAD16 PRINT_PTR, (START_REGION_COLOR_RAM + SCREEN_COLS)
        LOAD16 TMP_PTR, START_REGION_COLOR_RAM

        JSR copy_vram_block

        ; --------------------------------------------------------------------
        ; Step 3: Clear Bottom Row
        ; --------------------------------------------------------------------
        LDY #(SCREEN_COLS - 1)
@clear_bottom:

        LDA #DEFAULT_SCREEN_CHAR
        STA START_REGION_CHAR_RAM + BOTTOM_ROW_OFFSET,Y
        LDA CURRENT_COLOR
        STA START_REGION_COLOR_RAM + BOTTOM_ROW_OFFSET,Y
        DEY

        BPL @clear_bottom

        ; Clamp cursor to bottom row
        LDA #(SCREEN_ROWS - 1)
        STA CURSY

        POP_PTR TMP_PTR
        POP_PTR PRINT_PTR
        POPALL
        RTS
.endproc

; ----------------------------------------------------------------------------
; Internal Helper: Copies TOTAL_SCROLL_BYTES from PRINT_PTR to TMP_PTR
; ----------------------------------------------------------------------------
.proc copy_vram_block
        ; --- Copy Full 256-byte Pages ---
        LDX #PAGES_TO_COPY
        LDY #$00
@page_loop:
        LDA (PRINT_PTR),Y
        STA (TMP_PTR),Y
        INY
        BNE @page_loop
        INC PRINT_PTR + 1
        INC TMP_PTR + 1
        DEX
        BNE @page_loop

        ; --- Copy Remaining Bytes ---
        LDY #$00
@rem_loop:
        LDA (PRINT_PTR),Y
        STA (TMP_PTR),Y
        INY
        CPY #REM_BYTES_TO_COPY  ; Evaluates to $C0 (192)
        BNE @rem_loop

        RTS
.endproc

; ============================================================================
; Routine: SET_CURSOR
; Description:
;   Plots a single character to the screen at position (CURSX, CURSY) and updates
;   the corresponding tile in Color RAM with CURRENT_COLOR.
;
; Inputs:
;   CURSX      - Screen X coordinate (0 - 39)
;   CURSY      - Screen Y coordinate (0 - 24)
;
; Zero Page Working Registers:
;   CHAR_PTR   - Holds 16-bit target address in Character RAM
;   COLOR_PTR  - Holds 16-bit target address in Color RAM
;   TMP_PTR     - Temporary 16-bit scratch buffer for row offset math
; ============================================================================
.proc SET_CURSOR
        ;; -------------------------------------------------------------------
        ;; Step 1: Calculate Row Offset = (CURSY * 40)
        ;;
        ;; Since the 6502 lacks a hardware multiply instruction, we decompose
        ;; 40 into powers of two: 40 = 32 + 8 = (Y * 32) + (Y * 8).
        ;; We calculate (Y * 8) first via 3 bitwise left shifts (ASL/ROL).
        ;; -------------------------------------------------------------------
        LDA CURSY
        STA CHAR_PTR            ; Initialize low byte accumulator
        LDA #$00
        STA CHAR_PTR + 1        ; Initialize high byte accumulator

        ASL16 CHAR_PTR
        ASL16 CHAR_PTR
        ASL16 CHAR_PTR

        ;; Save intermediate result (CURSY * 8) into temporary zero-page storage
        MOV16 TMP_PTR, CHAR_PTR

        ;; Shift two more times: (CURSY * 8) * 4 = (CURSY * 32)
        ASL16 CHAR_PTR
        ASL16 CHAR_PTR

        ;; Add (CURSY * 8) to (CURSY * 32) to yield (CURSY * 40)
        ADD16 CHAR_PTR, CHAR_PTR, TMP_PTR

        ;; -------------------------------------------------------------------
        ;; Step 2: Add Column Offset (CURSX)
        ;; -------------------------------------------------------------------
        ADD16_8 CHAR_PTR, CHAR_PTR, CURSX
 
        ;; -------------------------------------------------------------------
        ;; Step 3: Compute Base Pointers
        ;;
        ;; 3a. Add START_REGION_CHAR_RAM ($E000) to complete CHAR_PTR
        ;; -------------------------------------------------------------------
        ADD16I CHAR_PTR, CHAR_PTR, START_REGION_CHAR_RAM

        ;; 3b. Derive COLOR_PTR from CHAR_PTR
        SUB16I COLOR_PTR, CHAR_PTR, (START_REGION_CHAR_RAM - START_REGION_COLOR_RAM)

        RTS
.endproc

.proc SET_CURSOR_OLD_KEEP

        ;; -------------------------------------------------------------------
        ;; Step 1: Calculate Row Offset = (CURSY * 40)
        ;;
        ;; Since the 6502 lacks a hardware multiply instruction, we decompose
        ;; 40 into powers of two: 40 = 32 + 8 = (Y * 32) + (Y * 8).
        ;; We calculate (Y * 8) first via 3 bitwise left shifts (ASL/ROL).
        ;; -------------------------------------------------------------------
        LDA CURSY
        STA CHAR_PTR            ; Initialize low byte accumulator
        LDA #$00
        STA CHAR_PTR + 1        ; Initialize high byte accumulator

        ASL CHAR_PTR            ; CHAR_PTR = CURSY * 2
        ROL CHAR_PTR + 1
        ASL CHAR_PTR            ; CHAR_PTR = CURSY * 4
        ROL CHAR_PTR + 1
        ASL CHAR_PTR            ; CHAR_PTR = CURSY * 8
        ROL CHAR_PTR + 1

        ;; Save intermediate result (CURSY * 8) into temporary zero-page storage
        LDA CHAR_PTR
        STA TMP_PTR
        LDA CHAR_PTR + 1
        STA TMP_PTR + 1

        ;; Shift two more times: (CURSY * 8) * 4 = (CURSY * 32)
        ASL CHAR_PTR            ; CHAR_PTR = CURSY * 16
        ROL CHAR_PTR + 1
        ASL CHAR_PTR            ; CHAR_PTR = CURSY * 32
        ROL CHAR_PTR + 1

        ;; Add (CURSY * 8) to (CURSY * 32) to yield (CURSY * 40)
        CLC
        LDA CHAR_PTR
        ADC TMP_PTR
        STA CHAR_PTR
        LDA CHAR_PTR + 1
        ADC TMP_PTR + 1
        STA CHAR_PTR + 1

        ;; -------------------------------------------------------------------
        ;; Step 2: Add Column Offset (CURSX)
        ;; -------------------------------------------------------------------
        CLC
        LDA CHAR_PTR
        ADC CURSX
        STA CHAR_PTR
        LDA CHAR_PTR + 1
        ADC #$00                ; Propagate 16-bit carry from low byte addition
        STA CHAR_PTR + 1

        ;; -------------------------------------------------------------------
        ;; Step 3: Compute Base Pointers
        ;;
        ;; 3a. Add START_REGION_CHAR_RAM ($E000) to complete CHAR_PTR
        ;; -------------------------------------------------------------------
        CLC
        LDA CHAR_PTR
        ADC #<START_REGION_CHAR_RAM
        STA CHAR_PTR
        LDA CHAR_PTR + 1
        ADC #>START_REGION_CHAR_RAM
        STA CHAR_PTR + 1

        ;; 3b. Derive COLOR_PTR from CHAR_PTR
        ;; Since START_REGION_COLOR_RAM ($C000) is $2000 bytes below
        ;; START_REGION_CHAR_RAM ($E000), subtract $2000 from CHAR_PTR.
        SEC
        LDA CHAR_PTR
        SBC #<(START_REGION_CHAR_RAM - START_REGION_COLOR_RAM)
        STA COLOR_PTR
        LDA CHAR_PTR + 1
        SBC #>(START_REGION_CHAR_RAM - START_REGION_COLOR_RAM)
        STA COLOR_PTR + 1

        RTS
.endproc


.proc CLEAR_SCREEN
        LOAD16 TMP_PTR, START_REGION_CHAR_RAM
        LOAD16 PRINT_PTR, END_REGION_CHAR_RAM

        LDA #DEFAULT_SCREEN_CHAR        ; Fill value
        JSR MEMFILL_SLOW

        LOAD16 TMP_PTR, START_REGION_COLOR_RAM
        LOAD16 PRINT_PTR, END_REGION_COLOR_RAM

        LDA #DEFAULT_COLOR        ; Fill value
        JSR MEMFILL_SLOW

        LDX #$00
        STX CURSX
        STX CURSY

        RTS
.endproc


.proc MEMFILL_FAST
        TAX                 ; X = fill byte

        ; --------------------------------------------------------------------
        ; Phase 1: Clear partial start page up to the $xx00 boundary
        ; --------------------------------------------------------------------
        LDY #$00
@ALIGN_LOOP:
        LDA TMP_PTR          ; Check if low byte is $00 (page aligned)
        BEQ @FILL_PAGES     ; If TMP_PTR points to $xx00, head alignment is done!

        ; Check if TMP_PTR has already hit PRINT_PTR before we finish aligning
        CMP PRINT_PTR
        BNE @ALIGN_WRITE
        LDA TMP_PTR+1
        CMP PRINT_PTR+1
        BEQ @DONE           ; Reached PRINT_PTR during alignment phase!

@ALIGN_WRITE:
        TXA
        STA (TMP_PTR),Y      ; Write fill byte at offset 0
        INC TMP_PTR          ; Advance low byte
        JMP @ALIGN_LOOP

        ; --------------------------------------------------------------------
        ; Phase 2: Clear whole 256-byte pages
        ; --------------------------------------------------------------------
@FILL_PAGES:
        LDA TMP_PTR+1
        CMP PRINT_PTR+1
        BEQ @FILL_REMAINDER ; High bytes match -> only partial tail page left!

        TXA
@PAGE_LOOP:
        STA (TMP_PTR),Y      ; Write byte at (TMP_PTR) + Y
        INY                 ; 8-bit increment (very fast!)
        BNE @PAGE_LOOP      ; Loops 256 times until Y wraps back to $00

        INC TMP_PTR+1        ; Advance to next 256-byte page
        JMP @FILL_PAGES

        ; --------------------------------------------------------------------
        ; Phase 3: Clear the remaining partial page
        ; --------------------------------------------------------------------
@FILL_REMAINDER:
        ; Y is currently $00. We fill from $00 up to PRINT_PTR low byte.
        TXA
@TAIL_LOOP:
        CPY PRINT_PTR          ; Reached remaining byte count?
        BEQ @DONE
        STA (TMP_PTR),Y      ; Write remaining bytes
        INY
        JMP @TAIL_LOOP

@DONE:
        RTS
.endproc

.proc MEMFILL_SLOW
        TAX             ; Save fill value in X
        LDY #$00

@LOOP:
        TXA
        STA (TMP_PTR),Y  ; Write byte

        ; Move to next byte
        INC TMP_PTR
        BNE @CHECK_END  ; If no rollover ($FF -> $00), skip high byte bump
        INC TMP_PTR+1

@CHECK_END:
        ; Compare current pointer with PRINT_PTR
        LDA TMP_PTR
        CMP PRINT_PTR
        BNE @LOOP
        LDA TMP_PTR+1
        CMP PRINT_PTR+1
        BNE @LOOP

        RTS
.endproc

; ============================================================================
; Reset Handler
; ============================================================================
_reset_handler:
        SEI             ; Disable interrupts
        LDX #$FF
        TXS             ; Reset stack pointer to $01FF
        CLD             ; Clear decimal flag

        JSR CLEAR_SCREEN

        LDY #$A2
        STY CURRENT_COLOR
        LDY #$10
        LDA #'-'
ll:
        STY CURSX
        STY CURSY
        PUSHALL
        JSR DISPLAY_CHAR
        POPALL

        DEY
        BPL ll

        ; Set pointer in Zero Page
        LOAD16 PRINT_PTR, msg_welcome

        ; Set desired start position & color
        LDA #5
        STA CURSX
        LDA #2
        STA CURSY
        LDA #$0F                ; White text
        STA CURRENT_COLOR

        LDA #'!'
        STA $E3C0 - 40

        LDX #$27 + 1
ploop:
        PUSHALL
        JSR PRINT_PSTRING
        POPALL
        DEX
        BNE ploop

halt:
        JMP halt        ; Safely trap CPU here when done


msg_welcome:
    pstring "Welcome to Yahtzee A8!"


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
JTCLS:  JMP CLEAR_SCREEN
