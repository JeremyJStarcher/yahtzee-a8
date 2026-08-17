# yahtzee-a8 (app)

Atari 800 / FCON userland for a Yahtzee game. This directory holds everything that runs **above** the BIOS: the host test image, its assembly suites, and the Python driver that builds, runs, and tests it under the sibling emulator at [`../fconsole`](../fconsole).

## Layout

```
app/
  build.py               User-land driver: assemble/link/disassemble/run/test (see below)
  hosts/                 6502 sources built against the kernel .inc mirrors
    fcon.cfg             Linker config: ZP $0050+$25 (37 B), CODE @ $0300, vectors hi-RAM
    fconsole.asm         Top level; single consolidated ZEROPAGE + budget assert
    shared/*.inc         MIRROR copies of the kernel headers (kept byte-identical on purpose*)
    shared/*_tests.asm   Branch-macro and math macro test suites (assembled into the image)
    output/<image>/      Build products per target (<dir>/output/<image>: .o/.lst/.map/.dbg/.lbl/.bin/.disasm.asm, gitignored)
  headless-run/          Text-only runner used by `macro-tests`; no GUI deps
  tools/inc_drift_check.py   Fails if any mirror copy drifted from its kernel original
  plans/                 Improvement plan + golden baseline capture
  ../fconsole            Kernel tree: bios/, inc/, lib6502/ — separate build.py driver
  ../tools/inc_drift_check.py  Same drift checker, run from the kernel side too
```

\* **Why the `.inc` files are duplicated instead of symlinked:** each tree is assembled with a self-contained include path so either can be built or shipped independently. The cost of duplication is drift risk, which [`inc_drift_check`](../tools/inc_drift_check.py) closes: it compares each `hosts/shared/*.inc` against `../fconsole/inc/*.inc` and runs in both drivers' `test` targets. When editing a header, change the **kernel** file first, then sync the mirror, then run the check.

## Commands (from this directory)

| Command | What it does |
|---|---|
| `./build.py fconsole` | Assemble → link → da65 disassemble the host image (`hosts/output/fconsole/fconsole.bin`) |
| `./build.py all` / `clean` | Build every target / drop artifacts |
| `./build.py macro-tests` | Build the test image and run it headless under BIOS; exits non-zero on any suite failure |
| `./build.py test` | Everything testable: Python checks + drift check + headless macro run |
| `./build.py run` | GUI-less BIOS boot (raw image at $F000, no user program loaded yet) |
| `./build.py run-text` | Headless text renderer for the loaded host image — watch test suites scroll by |
| `./build.py run-tk`, `run-pygame` | Tk bitmap / pygame renderers of the same thing |
| `lint` / `format` / `typecheck` / `format-asm` | ruff + pyrefly scoped to this tree; ruff format; pyrefly; asm whitespace normalizer |

The emulator itself lives in [`../fconsole`](../fconsole); its own `build.py` there builds **BIOS** targets and runs the machine. This driver never touches BIOS sources.

## Image formats

Two distinct binary shapes exist, and mixing them up is a classic foot-gun:

1. **Raw BIOS image** — pure 4 KB ROM contents flashed to `$F000`. What the kernel driver's build emits and what `run` boots.
2. **Loadable user image** — produced here as `hosts/output/fconsole/fconsole.bin`: `[load_addr:u16][start_ptr:u16][code...]` little-endian header followed by program bytes, placed into RAM at runtime (currently $0300, start pointer published via the bus flags at $0203–$0204). The headless runner resolves label addresses from `hosts/output/fconsole/fconsole.lbl` rather than hardcoding offsets, so ZEROPAGE may move without breaking it.

## Zero-page budget

All scratch space for the whole program is declared in one place near the top of [`hosts/fconsole.asm`](hosts/fconsole.asm), with a link-time `.assert` against the linker-defined `__ZP_START__`/`__ZP_SIZE__` (from [`fcon.cfg`](hosts/fcon.cfg)). Oversubscribing fails the **link**, not the run. Current usage is ~10 of the 37 available bytes.

## Macro-test flow

`shared/branch_tests.asm` and `shared/math_tests.asm` each emit self-printing pass/fail lines through BIOS `JTSTROUT`, latch a zero-page fail flag, and freeze on first failure (the runner detects the frozen PC). A green build ends with all suites printed and the machine HALT; any failure stops progress and makes both the direct runner and `./build.py test` exit non-zero.
