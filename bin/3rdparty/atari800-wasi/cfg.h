#ifndef CFG_H_
#define CFG_H_

/* cfg.h - WASI stub for the Atari800 core's config-file interface.
 *
 * The Windows port stores configuration in the registry.  For WASI we
 * simply provide the CFG_*_filename globals (ROM image paths) plus
 * no-op config load/save/search.  The WASI glue (atari800-wasi.c) sets
 * the ROM paths to a WASI-preopened /roms directory before calling
 * Atari800_Initialise().
 */

#include <stdio.h>
#include "util.h"

/* Paths to ROM images.  Initialised in cfg.c. */
extern char CFG_osa_filename[FILENAME_MAX];
extern char CFG_osb_filename[FILENAME_MAX];
extern char CFG_xlxe_filename[FILENAME_MAX];
extern char CFG_5200_filename[FILENAME_MAX];
extern char CFG_basic_filename[FILENAME_MAX];

/* Compares the string PARAM with each entry in the CFG_STRINGS array
   (of size CFG_STRINGS_SIZE), and returns the index under which PARAM is
   found.  If PARAM does not exist in CFG_STRINGS, returns a value lower
   than 0.  String comparison is case-insensitive. */
int CFG_MatchTextParameter(char const *param, char const * const cfg_strings[], int cfg_strings_size);

/* Load configuration from a file (WASI: always fails -> defaults used).
   Returns FALSE if the file was not found. */
int CFG_LoadConfig(const char *filename);

/* Save configuration to a file (WASI: no-op). */
void CFG_WriteConfig(void);

/* Search DIR (recursively if RECURSE) for ROM images and update the
   CFG_*_filename globals (WASI: no-op; ROMs come from a preopened dir). */
void CFG_FindROMImages(const char *dir, int recurse);

#endif /* CFG_H_ */
