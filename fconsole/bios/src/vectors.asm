; Interrupt Vector Table at $FFFA-$FFFF
        .import _reset_handler
        .import _nmi_handler
        .import _irq_handler
        .forceimport JTCLS
        .forceimport JTDUMMY
        .forceimport CURSX
        .forceimport CURSY

        .segment "VECTORS"
        .word   _nmi_handler        ; $FFFA - NMI vector
        .word   _reset_handler      ; $FFFC - RESET vector
        .word   _irq_handler        ; $FFFE - IRQ/BRK vector
