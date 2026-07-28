

.proc SET_CURSOR_FIXED_40

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

