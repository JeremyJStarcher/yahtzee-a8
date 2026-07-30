#!/usr/bin/env bash
# apply_cc65_wasi_patches.sh — Apply the maintained WASI portability patch set
#
# This script is idempotent: it checks whether each patch is already applied
# before attempting to apply it.  Run from the repository root.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
PATCH_DIR="$SCRIPT_DIR/../patches/cc65-wasi"

echo "=== Applying cc65 WASI portability patches ==="

for patch in "$PATCH_DIR"/*.patch; do
    patch_name="$(basename "$patch")"
    echo "  Checking $patch_name..."

    # --dry-run with --reverse tells us if the patch is already applied
    if patch -p1 --dry-run --reverse --force -d "$PROJECT_ROOT" < "$patch" > /dev/null 2>&1; then
        echo "    Already applied, skipping."
    else
        echo "    Applying..."
        patch -p1 --force -d "$PROJECT_ROOT" < "$patch"
        echo "    Done."
    fi
done

echo "=== Patches applied ==="
