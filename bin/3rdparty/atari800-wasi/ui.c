/*
 * ui.c - minimal UI stubs for the WASI build.
 *
 * The full Atari800 UI (menus, dialogs) is not used in the headless WASI
 * module; we only implement the symbols the core references unconditionally.
 */

#include "ui.h"

int UI_is_active = 0;
int UI_alt_function = UI_MENU_MONITOR;

int UI_SelectCartType(int type)
{
    (void) type;
    /* Cartridges are not used in the WASI build. */
    return 0; /* CARTRIDGE_NONE */
}

void UI_Run(void)
{
    /* No UI in the headless WASI module; the menu key is a no-op. */
}
