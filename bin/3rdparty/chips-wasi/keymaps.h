/* keymaps.h — pygame key constant → Commodore key code mapping tables.
 *
 * The Commodore key codes match those registered in:
 *   _vic20_init_key_map() in chips/systems/vic20.h
 *   _c64_init_key_map()  in chips/systems/c64.h
 *
 * Printable ASCII codes are passed directly; this header only needs to
 * define the special-case codes for function keys, cursor keys, etc.
 *
 * Note: pygame KEYDOWN events deliver lowercase ASCII for letter keys
 * (e.g., pygame.K_a = 97).  The Commodore keyboard matrix uses ASCII
 * values for printable characters, and special codes for everything else.
 *
 * The Python hosts build their lookup dicts using these #defines so the
 * C and Python sides stay in sync without duplicating magic numbers.
 */

#ifndef KEYMAPS_H_
#define KEYMAPS_H_

/* ── Commodore key codes (same for VIC-20 and C64) ──────────────────── */

#define CBM_KEY_DEL      0x01
#define CBM_KEY_CTRL     0x0E
#define CBM_KEY_CBM      0x0F   /* C= key (C64 only) */
#define CBM_KEY_STOP     0x03   /* RUN/STOP */
#define CBM_KEY_RETURN   0x0D
#define CBM_KEY_CSRLEFT  0x08   /* cursor left / backspace */
#define CBM_KEY_CSRRIGHT 0x09   /* cursor right */
#define CBM_KEY_CSRDOWN  0x0A   /* cursor down */
#define CBM_KEY_CSRUP    0x0B   /* cursor up */
#define CBM_KEY_HOME     0x0C   /* HOME (C64 only) */
#define CBM_KEY_CLR      0x02   /* CLR (shift+home, C64 only) */
#define CBM_KEY_LEFTARROW 0x04  /* left-arrow symbol (C64 only) */
#define CBM_KEY_INST     0x10   /* INST (shift+del, C64 only) */
#define CBM_KEY_RESTORE  0xFF   /* RESTORE key */
#define CBM_KEY_F1       0xF1
#define CBM_KEY_F2       0xF2
#define CBM_KEY_F3       0xF3
#define CBM_KEY_F4       0xF4
#define CBM_KEY_F5       0xF5
#define CBM_KEY_F6       0xF6
#define CBM_KEY_F7       0xF7
#define CBM_KEY_F8       0xF8

/* ── pygame → Commodore mapping as a comment key for the Python host ──
 *
 * Python equivalent (copy into host file):
 *
 * _KEY_MAP = {
 *     # modifiers
 *     pygame.K_LSHIFT:   -1,  # handled separately
 *     pygame.K_RSHIFT:   -1,
 *     pygame.K_LCTRL:    CBM_KEY_CTRL,
 *     pygame.K_RCTRL:    CBM_KEY_CTRL,
 *     pygame.K_LALT:     CBM_KEY_CBM,  # C= key (C64)
 *     pygame.K_RALT:     CBM_KEY_CBM,
 *     pygame.K_LMETA:    CBM_KEY_CBM,  # Super/Windows key too
 *     pygame.K_RMETA:    CBM_KEY_CBM,
 *
 *     # special keys
 *     pygame.K_RETURN:   CBM_KEY_RETURN,
 *     pygame.K_BACKSPACE: CBM_KEY_CSRLEFT,
 *     pygame.K_DELETE:   CBM_KEY_DEL,
 *     pygame.K_UP:       CBM_KEY_CSRUP,
 *     pygame.K_DOWN:     CBM_KEY_CSRDOWN,
 *     pygame.K_LEFT:     CBM_KEY_CSRLEFT,
 *     pygame.K_RIGHT:    CBM_KEY_CSRRIGHT,
 *     pygame.K_HOME:     CBM_KEY_HOME,
 *     pygame.K_END:      CBM_KEY_CLR,    # shift+home = clear
 *     pygame.K_INSERT:   CBM_KEY_INST,
 *     pygame.K_SPACE:    0x20,
 *     pygame.K_ESCAPE:   CBM_KEY_STOP,   # RUN/STOP
 *     pygame.K_BACKQUOTE:CBM_KEY_LEFTARROW,  # ` acts as left-arrow
 *
 *     # function keys
 *     pygame.K_F1:  CBM_KEY_F1,
 *     pygame.K_F2:  CBM_KEY_F2,
 *     pygame.K_F3:  CBM_KEY_F3,
 *     pygame.K_F4:  CBM_KEY_F4,
 *     pygame.K_F5:  CBM_KEY_F5,
 *     pygame.K_F6:  CBM_KEY_F6,
 *     pygame.K_F7:  CBM_KEY_F7,
 *     pygame.K_F8:  CBM_KEY_F8,
 * }
 *
 * # Printable keys: the host sends the INVERTED case of what the user types
 * # (via event.unicode), because chips registers UPPERCASE as the unshifted
 * # letter identifier and lowercase as the shifted one:
 * #   typing 'a' (no shift)  -> 65 ('A')  -> 'A' on screen
 * #   typing 'A' (shift)     -> 97 ('a')  -> graphics on VIC-20, 'a' on C64
 * #   pygame.K_0 = 48 -> 48 ('0')
 * #   Shift+1 -> '!' = 0x21 (shifted identifier -> '!')
 * # ALT / Super -> C= key (0x0F); on the C64, C= + letter gives graphics.
 */

#endif /* KEYMAPS_H_ */