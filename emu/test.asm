
 define  START_PTR $00 
 define S_H $01
 define  END_PTR $02
 define E_H $03

LDA #$30
STA S_H
LDA #$01
STA START_PTR



LDA #$30
STA E_H
LDA #$05
STA END_PTR

lda #$AF


memfill:
    tax             ; Save fill byte in X (A is clobbered by comparisons)
    ldy #$00        ; Y stays 0 for (START_PTR),Y addressing

loop:
    ; ---------- Check for end (exclusive) ----------
    lda START_PTR
    cmp END_PTR
    bne write      ; Low bytes differ → not at end yet
    lda S_H
    cmp E_H
    beq done       ; High bytes also equal → START_PTR == END_PTR, stop

write:
    ; ---------- Write the fill byte ----------
    txa             ; Retrieve fill byte from X
    sta (START_PTR), y

    ; ---------- Increment 16‑bit pointer ----------
    inc START_PTR
    bne loop       ; No low‑byte rollover → loop
    inc S_H ; Rollover from $FF to $00 → bump high byte
    jmp loop

done:
    rts
 


