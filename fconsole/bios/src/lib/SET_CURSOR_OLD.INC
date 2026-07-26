; This is the old version of SET_CURSOR
; It uses exactly the same logic and even compiles down to exactly the same bytes
; as the new version.



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


; Isn't this version *SO* much better?


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
