#ifndef CONFIG_H_
#define CONFIG_H_

/* config.h - Atari800 core configuration for the WASI / wasmtime build.
 *
 * Adapted from Atari800Win-PLus/Include/config.h for a pure-WASI target
 * compiled with emcc (-sSTANDALONE_WASM=1) and wasi-libc:
 *   - no SDL / DirectX / Windows
 *   - no sound in milestone 1 (pokeysnd/mzpokeysnd/sndsave not compiled)
 *   - no crash menu, no signal handling, no zlib/png, no network devices
 *   - POSIX-ish feature macros provided by wasi-libc are enabled
 *
 * The WASI glue (atari800-wasi.c) supplies PLATFORM_*, CFG_* and UI_*
 * symbols referenced by the core.
 */

/* ------------------------------------------------------------------ */
/* Targets / front-ends that must be OFF                               */
/* ------------------------------------------------------------------ */
#undef __PLUS            /* Atari800Win PLus-specific code paths */
#undef SDL
#undef DIRECTX
#undef DONT_DISPLAY      /* we want Atari800_display_screen set each frame */
#undef CRASH_MENU
#undef CURSES_BASIC
#undef USE_CURSES
#undef USE_NCURSES
#undef VERY_SLOW
#undef BASIC

/* ------------------------------------------------------------------ */
/* Sound (off in milestone 1; re-enable with POKEY audio later)        */
/* ------------------------------------------------------------------ */
#undef SOUND
#undef STEREO_SOUND
#undef SERIO_SOUND
#undef CONSOLE_SOUND
#undef VOL_ONLY_SOUND
#undef SYNCHRONIZED_SOUND
#undef CLIP_SOUND
#undef INTERPOLATE_SOUND
#undef NONLINEAR_MIXING
#undef SUPPORTS_SOUND_REINIT

/* ------------------------------------------------------------------ */
/* Optional hardware / devices (off)                                   */
/* ------------------------------------------------------------------ */
#undef PBI_BB
#undef PBI_MIO
#undef PBI_XLD
#undef PBI_PROTO80
#undef VOICEBOX
#undef AF80
#undef XEP80_EMULATION
#undef NTSC_FILTER
#undef IDE
#undef R_IO_DEVICE
#undef R_SERIAL
#undef R_NETWORK
#undef DOS_DRIVES
#undef LINUX_JOYSTICK

/* ------------------------------------------------------------------ */
/* Monitor / debugger features (off for a small module)                */
/* ------------------------------------------------------------------ */
#undef MONITOR_ASSEMBLER
#undef MONITOR_BREAK
#undef MONITOR_BREAKPOINTS
#undef MONITOR_HINTS
#undef MONITOR_PROFILE
#undef MONITOR_TRACE
#undef MONITOR_READLINE

/* ------------------------------------------------------------------ */
/* Event recording / profiling (off)                                   */
/* ------------------------------------------------------------------ */
#undef EVENT_RECORDING
#undef STAT_UNALIGNED_WORDS
#undef BENCHMARK

/* ------------------------------------------------------------------ */
/* Platform support macros                                             */
/* ------------------------------------------------------------------ */
/* Provide PLATFORM_Sleep() (no-op; the Python host paces timing).     */
#define SUPPORTS_PLATFORM_SLEEP 1
/* We read Colours_table directly each frame, so no palette callback.  */
#undef SUPPORTS_PLATFORM_PALETTEUPDATE
#undef SUPPORTS_PLATFORM_CONFIGSAVE
#undef SUPPORTS_PLATFORM_CONFIGURE
#undef SUPPORTS_CHANGE_VIDEOMODE
#undef SUPPORTS_ROTATE_VIDEOMODE

/* ------------------------------------------------------------------ */
/* Accuracy / architecture                                             */
/* ------------------------------------------------------------------ */
#define NEW_CYCLE_EXACT
#define WORDS_UNALIGNED_OK
#undef WORDS_BIGENDIAN
#undef PAGED_ATTRIB
#undef DIR_SEP_BACKSLASH

/* ------------------------------------------------------------------ */
/* Headers available in wasi-libc                                      */
/* ------------------------------------------------------------------ */
#define HAVE_STDIO_H
#define HAVE_STDLIB_H
#define HAVE_STRING_H
#define HAVE_ERRNO_H
#define HAVE_FCNTL_H
#define HAVE_UNISTD_H
#define HAVE_SYS_STAT_H
#define HAVE_SYS_TYPES_H
#define HAVE_SYS_TIME_H
#define HAVE_TIME_H
#define HAVE_DIRENT_H

/* ------------------------------------------------------------------ */
/* Standard C / POSIX functions available in wasi-libc                 */
/* ------------------------------------------------------------------ */
#define HAVE_ATEXIT
#define HAVE_FFLUSH
#define HAVE_FLOOR
#define HAVE_MODF
#define HAVE_MEMMOVE
#define HAVE_MEMSET
#define HAVE_STRCHR
#define HAVE_STRDUP
#define HAVE_STRERROR
#define HAVE_STRNCPY
#define HAVE_STRRCHR
#define HAVE_STRSTR
#define HAVE_STRTOL
#define HAVE_SNPRINTF
#define HAVE_VSNPRINTF
#define HAVE_VPRINTF

#define HAVE_GETTIMEOFDAY
#define HAVE_TIME
#define HAVE_LOCALTIME
#define HAVE_STAT
#define HAVE_FSTAT
#define HAVE_MKDIR
#define HAVE_MKSTEMP
#define HAVE_FDOPEN

/* shell-out / zlib / png deliberately NOT linked */
#undef HAVE_SYSTEM
#undef HAVE_LIBZ
#undef HAVE_LIBPNG

/* ------------------------------------------------------------------ */
/* Never-on platforms                                                  */
/* ------------------------------------------------------------------ */
#undef HAVE_WINDOWS_H
#undef HAVE_WINSOCK2_H
#undef HAVE_DIRECT_H
#undef HAVE_UNIXIO_H
#undef HAVE_FILE_H
#undef DJGPP
#undef PS2
#undef FALCON
#undef JAVANVM
#undef __EMX__
#undef __BEOS__

/* signal handling off */
#undef HAVE_SIGNAL
#undef HAVE_SIGNAL_H

/* sleep variants - we use SUPPORTS_PLATFORM_SLEEP instead */
#undef HAVE_NANOSLEEP
#undef HAVE_USLEEP
#undef HAVE_SELECT
#undef HAVE_UCLOCK
#undef HAVE_CLOCK

#endif /* CONFIG_H_ */
