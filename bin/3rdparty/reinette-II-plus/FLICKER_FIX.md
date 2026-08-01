# Flicker Fix

## Symptom
- Ghosting / reflections on screen after scrolling or mode switches.
- Text overlaying text; stale pixels persisting between frames.

## Root cause
The render loop used **dirty-cache** drawing: it only redrew cells whose cached value differed from current VRAM. This is fast but fragile — when the Apple II scrolls text it moves memory around, and the cache misses those moves because the *values* at each (line, col) haven’t changed yet. The result is leftover glyphs painted by an earlier frame.

A second issue was that switching between TEXT / GR / HGR didn’t invalidate the video caches, so pixels drawn in one mode could survive into another.

## What was changed
1. **TEXT mode now redraws every character every frame.**  
   The dirty-check (`TextCache[...] != glyph`) was removed from the text-render block. With only 960 glyphs this is trivially cheap and guarantees no stale characters ever appear.

2. **Mode-switch cache invalidation kept for HiRes/LoRes.**  
   A `prevTEXT/prevMIXED/prevPAGE2/prevHIRES` guard resets `HiResCache`, `LoResCache`, `previousBit` whenever a display-mode soft switch changes state, preventing cross-mode artifacts in graphics modes where full-frame repaint would be expensive.

3. **Per-frame clear removed.**  
   An earlier attempt added `SDL_RenderClear` each frame; that conflicted with dirty-cache rendering and left most cells black. The final version relies on complete overwrites in TEXT and correct invalidation in graphics modes instead.

## Result
- No more ghosting or text-on-text overlays after scrolling.
- Clean transitions when toggling TEXT / GR / HGR or PAGE2.
- Build verified: `gcc -std=c11 -pedantic -Wpedantic -Wall -O3 reinetteII+.c puce6502.c -lSDL2 -o reinetteII+` exits 0.
