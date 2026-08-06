#ifndef UI_H_
#define UI_H_

/* ui.h - minimal UI stubs for the WASI build.
 *
 * The full Atari800 UI (menus, dialogs) is not needed in the headless
 * WASI module.  We implement only the handful of symbols the core
 * references unconditionally.  In particular the AKEY_UI key (sent by
 * the host for a "menu" key) is handled as a no-op in ui.c.
 */

/* UI modes (value copied from the real ui.h). */
#define UI_MENU_MONITOR 7

extern int UI_is_active;
extern int UI_alt_function;

/* Called when an unknown cartridge type is auto-inserted.  Returns the
   cartridge type; we return CARTRIDGE_NONE (0) since cartridges are
   not used in the WASI build. */
int UI_SelectCartType(int type);

/* Runs the UI.  No-op in the headless WASI module. */
void UI_Run(void);

#endif /* UI_H_ */
