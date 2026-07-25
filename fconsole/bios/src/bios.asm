; Simple 6502 BIOS/Kernel Assembly Source
; Target: ca65 assembler from cc65 toolchain

        .export _irq_handler
        .export _reset_handler
        .export _nmi_handler
        .export JTCLS
        .export CURSX
        .export CURSY

        .segment "CODE"


SCREEN_COLS = 40
SCREEN_ROWS = 25

START_REGION_CHAR_RAM = $E000
END_REGION_CHAR_RAM   = START_REGION_CHAR_RAM + (40 * 25)

START_REGION_COLOR_RAM = $C000
END_REGION_COLOR_RAM   = START_REGION_COLOR_RAM + (40 * 25)

DEFAULT_COLOR = $6F
DEFAULT_SCREEN_CHAR = '='


        .segment "ZEROPAGE"
STRPTR: .res 2
ENDPTR: .res 2
FILCHAR: .res 1

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

.proc SET_CURSOR
        ;; We want to take the CURSX, CURSY
        ;; and convert them to a pointer within CHAR_PTR
        ;; Then, for a test, we'll write a '*' to that one
        ;; position to verify it works.

.endproc


.proc CLEAR_SCREEN
        PHA
        LDA #<START_REGION_CHAR_RAM
        STA STRPTR
        LDA #>START_REGION_CHAR_RAM
        STA STRPTR + 1

        LDA #<END_REGION_CHAR_RAM
        STA ENDPTR
        LDA #>END_REGION_CHAR_RAM
        STA ENDPTR + 1
        PLA

        LDA #DEFAULT_SCREEN_CHAR        ; Fill value
        JSR MEMFILL_SLOW

        PHA
        LDA #<START_REGION_COLOR_RAM
        STA STRPTR
        LDA #>START_REGION_COLOR_RAM
        STA STRPTR + 1

        LDA #<END_REGION_COLOR_RAM
        STA ENDPTR
        LDA #>END_REGION_COLOR_RAM
        STA ENDPTR + 1
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
        LDA STRPTR          ; Check if low byte is $00 (page aligned)
        BEQ @FILL_PAGES     ; If STRPTR points to $xx00, head alignment is done!

        ; Check if STRPTR has already hit ENDPTR before we finish aligning
        CMP ENDPTR
        BNE @ALIGN_WRITE
        LDA STRPTR+1
        CMP ENDPTR+1
        BEQ @DONE           ; Reached ENDPTR during alignment phase!

@ALIGN_WRITE:
        TXA
        STA (STRPTR),Y      ; Write fill byte at offset 0
        INC STRPTR          ; Advance low byte
        JMP @ALIGN_LOOP

        ; --------------------------------------------------------------------
        ; Phase 2: Clear whole 256-byte pages
        ; --------------------------------------------------------------------
@FILL_PAGES:
        LDA STRPTR+1
        CMP ENDPTR+1
        BEQ @FILL_REMAINDER ; High bytes match -> only partial tail page left!

        TXA
@PAGE_LOOP:
        STA (STRPTR),Y      ; Write byte at (STRPTR) + Y
        INY                 ; 8-bit increment (very fast!)
        BNE @PAGE_LOOP      ; Loops 256 times until Y wraps back to $00

        INC STRPTR+1        ; Advance to next 256-byte page
        JMP @FILL_PAGES

        ; --------------------------------------------------------------------
        ; Phase 3: Clear the remaining partial page
        ; --------------------------------------------------------------------
@FILL_REMAINDER:
        ; Y is currently $00. We fill from $00 up to ENDPTR low byte.
        TXA
@TAIL_LOOP:
        CPY ENDPTR          ; Reached remaining byte count?
        BEQ @DONE
        STA (STRPTR),Y      ; Write remaining bytes
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
        STA (STRPTR),Y  ; Write byte

        ; Move to next byte
        INC STRPTR
        BNE @CHECK_END  ; If no rollover ($FF -> $00), skip high byte bump
        INC STRPTR+1

@CHECK_END:
        ; Compare current pointer with ENDPTR
        LDA STRPTR
        CMP ENDPTR
        BNE @LOOP
        LDA STRPTR+1
        CMP ENDPTR+1
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

        LDY #$10
        STY CURSX
        STY CURSY
        JSR SET_CURSOR
halt:

        JMP halt        ; Safely trap CPU here when done

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
