# Video Display Component Specification

## Overview

Implement the video-display component for a simple 8-bit computer
emulator in Python.

The emulator is launched from the console, but the video subsystem opens
one or more graphical windows for display.

Use **Tkinter** as the GUI toolkit.

The design should support multiple simultaneous `Video` instances. Each
instance owns its own video memory and its own display window, allowing,
for example, a normal display and a debugging display.

------------------------------------------------------------------------

# Constructor

``` python
Video(rows, columns)
```

Both parameters must be positive integers.

Each display contains:

    rows × columns

character cells.

------------------------------------------------------------------------

# Display Geometry

Each logical character cell is **8 × 8 pixels**.

Logical screen size:

    width  = columns × 8
    height = rows × 8

The implementation may optionally support integer scaling (2×, 3×, etc.)
using nearest-neighbor scaling.

------------------------------------------------------------------------

# Video Memory

Each display owns two one-dimensional byte arrays.

``` text
screenMemory
colorMemory
```

Both arrays contain:

``` python
rows * columns
```

elements.

Addressing is row-major.

    offset = row * columns + column

Valid offsets are:

    0 .. (rows * columns - 1)

Invalid offsets should raise `IndexError`.

------------------------------------------------------------------------

# Character Memory

Character memory stores one unsigned byte per cell.

The byte indexes the following table after masking off the high bit.

    characterIndex = characterByte & 0x7F

Values from `0x80` through `0xFF` therefore display the same glyphs as
`0x00` through `0x7F`.

The character table is:

``` python
CHARS = [
    "♥","├","🮇","┘","┤","┐","╱","╲","◢","▗","◣","▝","▘","🮂","▂","▖",
    "♣","┌","─","┼","•","▄","▎","┬","┴","▌","└","␛","↑","↓","←","→",
    " ","!",'"',"#","$","%","&","'","(",")","*","+",",","-",".","/",
    "0","1","2","3","4","5","6","7","8","9",":",";","<","=",">","?",
    "@","A","B","C","D","E","F","G","H","I","J","K","L","M","N","O",
    "P","Q","R","S","T","U","V","W","X","Y","Z","[","\\","]","^","_",
    "♦","a","b","c","d","e","f","g","h","i","j","k","l","m","n","o",
    "p","q","r","s","t","u","v","w","x","y","z","♠","|","🢰","◀","▶",
]
```

Character memory must initially be filled with:

``` python
0x20
```

(the space character).

------------------------------------------------------------------------

# Color Memory

Each color byte is:

    Bits 7-4 : Background color
    Bits 3-0 : Foreground color

Use the following Commodore 64 palette:

``` python
C64_COLORS = [
    (0x00,0x00,0x00),
    (0xFF,0xFF,0xFF),
    (0x68,0x37,0x2B),
    (0x70,0xA4,0xB2),
    (0x6F,0x3D,0x86),
    (0x58,0x8D,0x43),
    (0x35,0x28,0x79),
    (0xB8,0xC7,0x6F),
    (0x6F,0x4F,0x25),
    (0x43,0x39,0x00),
    (0x9A,0x67,0x59),
    (0x44,0x44,0x44),
    (0x6C,0x6C,0x6C),
    (0x9A,0xD2,0x84),
    (0x6C,0x5E,0xB5),
    (0x95,0x95,0x95),
]
```

Initial color:

``` python
DEFAULT_COLOR = 0x67
```

This is:

-   Background: Blue (6)
-   Foreground: Yellow (7)

------------------------------------------------------------------------

# Public API

``` python
set_screen(offset, character)
set_color(offset, color)

get_screen(offset)
get_color(offset)

refresh_screen()

close()
```

`set_screen()` and `set_color()` only modify memory and mark the cell
dirty.

They **must not** redraw immediately.

All stored values should be masked with:

``` python
value & 0xFF
```

------------------------------------------------------------------------

# Screen Refresh

The emulator controls presentation by calling:

``` python
refresh_screen()
```

This method must:

1.  Redraw the display.
2.  Process pending Tkinter events.
3.  Keep the window responsive.
4.  Be safe to call when nothing changed.

The initial implementation may redraw the entire display every refresh.

Dirty-rectangle optimization may be added later.

------------------------------------------------------------------------

# Multiple Displays

Each `Video` instance owns:

-   its own window
-   screen memory
-   color memory
-   dirty state

Closing one display must not affect another.

------------------------------------------------------------------------

# Rendering Notes

Every character occupies one fixed 8×8 cell.

The implementation may initially render Unicode characters using a
monospaced font.

A future version may replace this with true 8×8 bitmap glyphs for
pixel-perfect rendering.

------------------------------------------------------------------------

# Error Handling

-   Invalid constructor dimensions -\> `ValueError`
-   Invalid offsets -\> `IndexError`
-   Non-numeric values -\> `TypeError`

------------------------------------------------------------------------

# Summary

The video subsystem intentionally separates **memory updates** from
**display refresh**.

Typical emulator loop:

``` python
cpu.execute()

video.set_screen(...)
video.set_color(...)

video.refresh_screen()
```

This keeps the emulator architecture simple while leaving room for
future optimizations.
