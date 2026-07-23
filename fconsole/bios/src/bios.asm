; Simple 6502 BIOS/Kernel Assembly Source
; Target: ca65 assembler from cc65 toolchain
; Memory Map:
;   Zero Page:    $00-$FF
;   RAM:          $2000-$DFFF  
;   ROM/BIOS:     $F000-$FFFF
;   Entry Point:  $F000 (_reset_handler)
;   Vectors:      $FFFA-$FFFF -> all point to $F000

; Export the reset handler so linker can find it
        .export _reset_handler

; Code is placed at the start of the ROM by the linker configuration.
        .segment "CODE"

; ============================================================================
; Reset Handler (Entry point at $F000)
; ============================================================================
_reset_handler:
        ; Disable interrupts during initialization
        sei

        ; Set stack pointer to $01FF (top of page 1)
        ldx #$FF
        txs

        ; Clear decimal mode for consistency
        cld

main_loop:
        jmp main_loop      ; Infinite loop - halt execution

; ============================================================================
; NMI Handler (Non-Maskable Interrupt) - returns immediately
; ============================================================================
_nmi_handler:
        rti                ; Return from interrupt

; ============================================================================
; IRQ/BRK Handler (Maskable Interrupt/Break) - returns immediately
; ============================================================================
_irq_handler:
        rti                ; Return from interrupt

; ============================================================================