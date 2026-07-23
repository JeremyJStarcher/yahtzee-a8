; Interrupt Vector Table at $FFFA-$FFFF
        .import _reset_handler
        .segment "VECTORS"
        .word   _reset_handler    ; $FFFA - NMI vector
        .word   _reset_handler    ; $FFFC - RESET vector
        .word   _reset_handler    ; $FFFE - IRQ/BRK vector