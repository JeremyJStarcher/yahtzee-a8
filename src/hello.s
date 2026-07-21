        .setcpu "6502"
        .include "atari.inc"

        .export start
        .segment "CODE"

start:
        ldx #$00
loop:
        lda message,x
        beq done
        stx $00
        ldy $00
        sta ($58), y
        ;sta $0400,x
        inx
        bne loop

done:
        jmp done

message:
        .byte "HELLO WORLD", 0
