; Simple 6502 BIOS/Kernel Assembly Source
; Target: ca65 assembler from cc65 toolchain

        .include "branches.inc"

        .export _irq_handler
        .export _reset_handler
        .export _nmi_handler
        .export JTCLS
        .exportzp CURSX
        .exportzp CURSY

        .segment "CODE"



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
; Routine: PRINT_STRING
; Description:
;   Prints a length-prefixed sequence of characters starting at TMP_PTR.
;   Advances CURSX (and CURSY via wrapping) automatically per character.
;
; Inputs:
;   TMP_PTR (2 bytes, Zero Page) - Pointer to character array/string payload
;   X                           - Length of string in bytes (0 - 255)
;
; Registers Modified:
;   A, X, Y
; ============================================================================
.proc PRINT_STRING
        CPX #$00
        BEQ @done               ; Early exit if length is 0

        LDY #$00                ; Initialize string index/offset
@loop:

        PUSHALL
        LDA (PRINT_PTR),Y         ; Fetch character at current offset
        JSR DISPLAY_CHAR        ; Draw character & advance CURSX / wrap row
        POPALL

        INY                     ; Move pointer index to next character
        DEX                     ; Decrement remaining byte count
        BNE @loop               ; Loop until X counts down to zero

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
        PHA                     ; Save input character (A) on the stack
        JSR SET_CURSOR          ; Calculate CHAR_PTR and COLOR_PTR for (CURSX, CURSY)

        ;; -------------------------------------------------------------------
        ;; Step 4: Write Memory Values
        ;; -------------------------------------------------------------------
        LDY #$00

        PLA                     ; Restore input character code into A
        STA (CHAR_PTR),Y        ; Write character to Character RAM

        LDA CURRENT_COLOR
        STA (COLOR_PTR),Y       ; Write color attribute to Color RAM

        ;; -------------------------------------------------------------------
        ;; Step 5: Advance Cursor Position
        ;; -------------------------------------------------------------------
        INC CURSX               ; Move cursor 1 column to the right

        LDA CURSX
        IF_A_GE 40, @wrap_row   ; If CURSX >= 40, advance to next row
        RTS

@wrap_row:
        JSR DISPLAY_NEXT_LINE   ; Reset X to 0 and increment Y
        RTS
.endproc


; ============================================================================
; Routine: DISPLAY_NEXT_LINE
; Description:
;   Resets CURSX to 0 and advances CURSY to the next line.
; ============================================================================
.proc DISPLAY_NEXT_LINE
        LDA #$00
        STA CURSX               ; Carriage return (X = 0)

        INC CURSY               ; Line feed (Y = Y + 1)
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
        PHA
        LDA #<START_REGION_CHAR_RAM
        STA TMP_PTR
        LDA #>START_REGION_CHAR_RAM
        STA TMP_PTR + 1

        LDA #<END_REGION_CHAR_RAM
        STA PRINT_PTR
        LDA #>END_REGION_CHAR_RAM
        STA PRINT_PTR + 1
        PLA

        LDA #DEFAULT_SCREEN_CHAR        ; Fill value
        JSR MEMFILL_SLOW

        PHA
        LDA #<START_REGION_COLOR_RAM
        STA TMP_PTR
        LDA #>START_REGION_COLOR_RAM
        STA TMP_PTR + 1

        LDA #<END_REGION_COLOR_RAM
        STA PRINT_PTR
        LDA #>END_REGION_COLOR_RAM
        STA PRINT_PTR + 1
        PLA

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
        LDA #<msg_hello
        STA PRINT_PTR
        LDA #>msg_hello
        STA PRINT_PTR + 1

        ; Set length counter in X
        LDX #MSG_HELLO_LEN

        ; Set desired start position & color
        LDA #5
        STA CURSX
        LDA #2
        STA CURSY
        LDA #$0F                ; White text
        STA CURRENT_COLOR

        JSR PRINT_STRING

halt:

        JMP halt        ; Safely trap CPU here when done



;; .segment "RODATA"
msg_hello:
        .byte "ZHello, Atari 800 BIOS!"
MSG_HELLO_LEN = * - msg_hello



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
