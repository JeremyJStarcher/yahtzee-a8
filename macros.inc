
.MACRO JMP_IF_X_IS
    ; IF_X_IS <value> JMP <address>
    CPX #%$1
    BNE SKIP?
    JMP %$2
SKIP?

.ENDM


.MACRO PUSHALL
        php           ; Push status register
        STA SAVEA     ; Save the 'A' register while storing the others
        pha           ; Push A
        txa           ; X -> A
	pha           ; Push X value in A
	tya           ; Y -> A
	pha           ; PUSH Y value in A
        LDA SAVEA     ; And get our original 'A' back
.ENDM

.MACRO POPALL
        PLA           ; Get the pushed Y value
        TAY           ; Transfer to Y
        PLA           ; Get the pushed X value
        TAX           ; Transfer to X
        PLA           ; And then get A
        plp           ; Pull status register
.ENDM


; PRINTPTR <address> - prints the address in tihe pointer.
.MACRO PRINTPTR
        PUSHALL

        LDY #$01
        LDA %$1,Y
        JSR P_BYTEOUT
        DEY
        LDA %$1,Y
        JSR P_BYTEOUT

        POPALL
.ENDM

;; Yes, these macros are brutal and dirty... but they are meant for debugging, so that's OK.
;; I'm not worried about them being bloated as long as they are easy to use.

.MACRO MAKE_OUTPUT_CONTROL
%$1_IOCB        .BYTE %$2
%$1_IOCB        .BYTE 1
%$1_ROW         .BYTE 1
%$1_COL_L       .BYTE 1
%$1_COL_H       .BYTE 1
%$1_LEN_L       .BYTE 1
%$1_LEN_H       .BYTE 1
%$1_PTR_L       .BYTE 1
%$1_PTR_H       .BYTE 1
.ENDM


.MACRO SHOW_RANGE
;       SHOW_RANGE DICE_START DICE_END

        LDY #%$2
LOOP?
        TYA
        JSR DISPLAY_MESSAGE
        DEY
        CPY #%$1
        BPL LOOP?
.ENDM

.MACRO SHOW_RANGE2
;       SHOW_RANGE DICE_START COUNT
        LDY #%$1
        LDX #%$2
LOOP?
        TYA
        JSR DISPLAY_MESSAGE
        INY
        DEX
        BNE LOOP?
.ENDM



.macro  inc16
        inc     %$1
        bne     Skip?
        inc     %$1+1
Skip?
.ENDM

