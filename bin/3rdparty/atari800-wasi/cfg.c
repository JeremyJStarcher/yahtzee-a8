/*
 * cfg.c - WASI implementation of the Atari800 core's config interface.
 *
 * The Windows port stores configuration in the registry; the WASI build
 * needs none of that.  We provide the CFG_*_filename globals (ROM image
 * paths) and no-op config load/save/search.  The WASI glue sets the ROM
 * paths to a WASI-preopened /roms directory before Atari800_Initialise().
 */

#include "atari.h"   /* FALSE, TRUE */
#include "cfg.h"
#include <ctype.h>
#include <string.h>

/* Start each path as "not set" (\n) so Atari800_Initialise fills in the
   built-in defaults if the glue leaves them alone. */
char CFG_osa_filename[FILENAME_MAX] = Util_FILENAME_NOT_SET;
char CFG_osb_filename[FILENAME_MAX] = Util_FILENAME_NOT_SET;
char CFG_xlxe_filename[FILENAME_MAX] = Util_FILENAME_NOT_SET;
char CFG_5200_filename[FILENAME_MAX] = Util_FILENAME_NOT_SET;
char CFG_basic_filename[FILENAME_MAX] = Util_FILENAME_NOT_SET;

/* Case-insensitive string compare (ASCII). */
static int wasi_stricmp(const char *a, const char *b) {
    while (*a && *b) {
        int ca = tolower((unsigned char) *a);
        int cb = tolower((unsigned char) *b);
        if (ca != cb)
            return ca - cb;
        a++;
        b++;
    }
    return tolower((unsigned char) *a) - tolower((unsigned char) *b);
}

int CFG_MatchTextParameter(char const *param, char const * const cfg_strings[], int cfg_strings_size)
{
    int i;
    for (i = 0; i < cfg_strings_size; i++) {
        if (wasi_stricmp(param, cfg_strings[i]) == 0)
            return i;
    }
    return -1;
}

int CFG_LoadConfig(const char *filename)
{
    (void) filename;
    return FALSE; /* no config file -> defaults are used */
}

void CFG_WriteConfig(void)
{
    /* no-op */
}

void CFG_FindROMImages(const char *dir, int recurse)
{
    (void) dir;
    (void) recurse; /* ROMs come from the preopened /roms dir */
}
