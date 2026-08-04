# Commodore WASI Emulators — Key Bindings

This documents how your PC keyboard maps to the VIC-20 / C64 when running
`vic20_host.py` or `c64_host.py` (the shared `commodore_host.py` pygame host).
Both emulators share the same host, so most bindings are identical; the few
machine-specific differences are called out below.

The emulator boots to BASIC `READY.` and the cursor sits on a fresh line.
Type a BASIC line and press `Return` to execute it.

---

## Quick reference

| PC key | Commodore function |
|--------|--------------------|
| `A`–`Z` (no shift) | Uppercase letters (e.g. `PRINT`, `RUN`) |
| `Shift` + `A`–`Z` | **VIC-20:** graphics symbol · **C64:** lowercase letter |
| `0`–`9`, `+ - * / , . ; : ' " ( )` etc. | The symbol on the key |
| `Shift` + number/symbol | The shifted symbol (e.g. `Shift+1` = `!`, `Shift+8` = `*`) |
| `Enter` / keypad `Enter` | `RETURN` (execute line) |
| `Backspace` | Cursor left (`CRSR ←`) |
| `Delete` | `DEL` |
| `Insert` | `INST` (C64) |
| `Home` | `HOME` |
| `End` | `CLR/HOME` (clear screen) |
| `Up` / `Down` / `Left` / `Right` | Cursor keys |
| `Escape` | `RUN/STOP` |
| `Ctrl` | The Commodore `CTRL` key |
| `Alt` (or `Super`) | The Commodore `C=` key (C64) |
| `F1`–`F8` | Function keys `F1`–`F8` |
| `` ` `` (backquote) | Left-arrow `←` (C64) |

---

## Typing & case behaviour

chips' keyboard identifiers are the *unshifted* matrix labels.  The host sends
the **inverted case** of what you type so normal typing produces readable
letters while `Shift` still reaches the alternate character set:

| You type | Sent to machine | VIC-20 shows | C64 shows |
|----------|-----------------|--------------|-----------|
| `a` (no shift) | `65` (`A`) | `A` | `A` |
| `A` (`Shift`+`a`) | `97` (`a`) | graphics symbol | `a` |

So typing `print "hello"` produces `PRINT "HELLO"` — exactly what BASIC wants.

---

## Special keys

| PC key | Sends | Notes |
|--------|-------|-------|
| `Enter` | `RETURN` (0x0D) | |
| `Backspace` | cursor left (0x08) | |
| `Delete` | `DEL` (0x01) | |
| `Insert` | `INST` (0x10) | C64 |
| `Home` | `HOME` (0x0C) | C64 |
| `End` | `CLR` (0x02) | `Shift`+`Home` = clear screen |
| `Escape` | `RUN/STOP` (0x03) | |
| `` ` `` | left arrow `←` (0x04) | C64 |
| `F1`–`F8` | `F1`–`F8` (0xF1–0xF8) | |

---

## Modifiers

### `Ctrl` — the Commodore CTRL key

`Ctrl` is passed through as the machine's `CTRL` key.  The KERNAL interprets
`Ctrl` + key as a *control code* (PETSCII `0x01`–`0x1A`):

- **C64:** `Ctrl` + `1`–`8` changes the text colour.  `Ctrl`+letter combos
  produce the corresponding control code — e.g. **`Ctrl`+`Q` = cursor down**,
  `Ctrl`+`M` = RETURN, `Ctrl`+`N` = lowercase mode, `Ctrl`+`C` = RUN/STOP.
- **VIC-20:** the Ctrl key is now detected by the machine (chips only defined
  the modifier there); colour changes and control codes work as on real
  hardware.

`Ctrl`+`Q` is **not** a quit — it is passed to the emulator (on the C64 it is
the *cursor down* control code).  To quit use `Ctrl`+`Shift`+`Q` or close the
window.

### `Shift` — graphics / lowercase

- **VIC-20** (uppercase/graphics charset): `Shift` + letter types a **graphics
  symbol**.
- **C64:** `Shift` + letter types a **lowercase** letter (the C64 boots in
  uppercase mode).

### `Alt` / `Super` — the `C=` (Commodore) key

`Alt` and the `Super`/`Windows` key act as the C64's `C=` key:

- **C64:** `Alt` + letter gives the alternate **graphics characters**
  (e.g. `Alt`+`A`).  `Alt` + `Shift` + key gives further alternates.
- **VIC-20:** there is no `C=` key, so `Alt` has no special meaning.

### Case mode (C64)

A `Ctrl` keystroke can switch the C64 between the uppercase/graphics and
lowercase character sets:

| To do this | Press |
|------------|-------|
| Switch to **lowercase** mode | `Ctrl` + `N` |
| Switch back to **uppercase/graphics** | `Ctrl` + `Shift` + `N` |

If you ever find yourself in lowercase mode and want out, press
**`Ctrl` + `Shift` + `N`**.

---

## Quitting

| Action | Result |
|--------|--------|
| `Ctrl` + `Shift` + `Q` | Quit the emulator |
| Close the window | Quit the emulator |

---

## Command-line options

Run either host headless for automated validation (no window):

```bash
python3 vic20_host.py --headless --type '10 PRINT"HI"\nRUN\n' --dump-text
python3 c64_host.py  --headless --type 'PRINT 3+4\n' --dump-text
```

| Option | Meaning |
|--------|---------|
| `--scale N` | pygame integer scale (VIC-20 default 3, C64 default 2) |
| `--fps N` | target frame rate (default 60) |
| `--headless` | run without a display |
| `--pre-frames N` | frames to run before typing (boot) |
| `--post-frames N` | frames to run after the last keystroke |
| `--key-frames N` | frames to hold each typed key (prevents keyboard-buffer overflow) |
| `--type "TEXT"` | text to type; `\n` / `\r` = RETURN |
| `--dump FILE.rgba` | write the raw RGBA framebuffer to a file |
| `--dump-text` | print the decoded text screen (from screen RAM) |
| `--preview` | print a coarse ASCII luminance preview |
| `--preview-cell N` | preview cell size in pixels |

---

## Notes

- Letters sent with no shift are uppercased because chips' unshifted
  identifiers are uppercase (see [`keymaps.h`](keymaps.h)).
- `Ctrl`+`letter` produces control codes (functions), which the KERNAL does
  not echo as glyphs at the prompt — this is correct Commodore behaviour.
- VIC-20 graphics come from `Shift`+letter; C64 graphics come from `Alt`/`C=`
  +letter.  There is no global "graphics mode" toggle in the host.
