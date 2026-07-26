; Two memory fill functions.


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
