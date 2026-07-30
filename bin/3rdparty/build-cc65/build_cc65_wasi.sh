#!/usr/bin/env bash
# build_cc65_wasi.sh — Compile cc65 host tools as WASI Preview 1 command modules.
#
# Maintainer / CI only.  End users consume the pre-built .wasm modules.
# Requires WASI SDK (https://github.com/WebAssembly/wasi-sdk).
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

# --- pinned toolchain ---
WASI_SDK_PATH="${WASI_SDK_PATH:-/opt/wasi-sdk}"
WASI_TARGET="${WASI_TARGET:-wasm32-wasip1}"
WASI_SYSROOT="$WASI_SDK_PATH/share/wasi-sysroot"

CLANG="$WASI_SDK_PATH/bin/clang"
LLVM_AR="$WASI_SDK_PATH/bin/llvm-ar"

# --- paths ---
CC65_ROOT="$PROJECT_ROOT/3rdparty/cc65"
OUTPUT_DIR="$PROJECT_ROOT/wasi"

# --- verify toolchain ---
for tool in "$CLANG" "$LLVM_AR"; do
    if [[ ! -x "$tool" ]]; then
        echo "ERROR: Required WASI SDK tool not found: $tool" >&2
        echo "Set WASI_SDK_PATH or install WASI SDK." >&2
        exit 1
    fi
done

if [[ ! -d "$WASI_SYSROOT" ]]; then
    echo "ERROR: WASI sysroot not found: $WASI_SYSROOT" >&2
    exit 1
fi

echo "=== Building cc65 as WASI Preview 1 commands ==="
echo "Target:   $WASI_TARGET"
echo "Sysroot:  $WASI_SYSROOT"
echo "Clang:    $($CLANG --version | head -n 1)"

# --- apply maintained WASI portability patches ---
"$SCRIPT_DIR/apply_cc65_wasi_patches.sh"

# --- clean previous build artefacts ---
make -C "$CC65_ROOT/src" clean 2>/dev/null || true
rm -rf "$CC65_ROOT/wrk" "$CC65_ROOT/bin"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# --- build ca65, ld65, da65 ---
# Path defines use Make variables so they survive the Makefile's own
# -D... append order (see CC65_WASI_DETAILED_BUILD_PLAN_v2.md §A5).
make -C "$CC65_ROOT/src" \
    CC="$CLANG" \
    AR="$LLVM_AR" \
    EXE_SUFFIX=".wasm" \
    CA65_INC=/cc65/asminc \
    CC65_INC=/cc65/include \
    CL65_TGT=/cc65/target \
    LD65_CFG=/cc65/cfg \
    LD65_LIB=/cc65/lib \
    LD65_OBJ=/cc65/lib \
    BUILD_ID="WASI 2.19" \
    USER_CFLAGS="--target=$WASI_TARGET --sysroot=$WASI_SYSROOT -O3" \
    LDFLAGS="--target=$WASI_TARGET --sysroot=$WASI_SYSROOT" \
    LDLIBS="-lm -lwasi-emulated-getpid" \
    ar65 ca65 cc65 chrcvt65 co65 da65 grc65 ld65 od65 sp65

# --- collect and validate ---
for tool in ar65 ca65 cc65 chrcvt65 co65 da65 grc65 ld65 od65 sp65; do
    src="$CC65_ROOT/bin/$tool.wasm"
    dst="$OUTPUT_DIR/$tool.wasm"

    if [[ ! -f "$src" ]]; then
        echo "ERROR: Expected build output missing: $src" >&2
        exit 1
    fi

    cp "$src" "$dst"
    echo "  Copied  $tool.wasm"
done

echo ""
echo "--- Module import/export validation ---"
python3 "$SCRIPT_DIR/verify_wasi_modules.py" "$OUTPUT_DIR"/*.wasm

echo ""
echo "=== WASI build complete ==="
ls -lh "$OUTPUT_DIR"
