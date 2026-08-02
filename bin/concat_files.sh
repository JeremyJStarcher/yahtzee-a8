#!/usr/bin/env bash

# Disable filename expansion (globbing) so that patterns from
# .concatfiles (e.g. "*.bin") are not expanded before being used
# in case-statement pattern matching.
set -f

# Usage check
if [ $# -ne 1 ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

# Resolve to an absolute path so the walk-up loop works with
# relative targets like "." or "../bios".
target_dir="$(cd "$1" 2>/dev/null && pwd)" || {
    echo "Error: '$1' is not an accessible directory" >&2
    exit 1
}

output_file="/tmp/all.txt"

# Start fresh
> "$output_file" || { echo "Error: cannot write to $output_file" >&2; exit 1; }

# Find all regular files, process them one by one
# Walk up the directory tree to find .concatfiles
ignore_file=""
_search_dir="$target_dir"
while true; do
    if [ -f "$_search_dir/.concatfiles" ]; then
        ignore_file="$_search_dir/.concatfiles"
        break
    fi
    _parent="$(dirname "$_search_dir")"
    [ "$_parent" = "$_search_dir" ] && break   # reached root
    _search_dir="$_parent"
done

find "$target_dir" -type f -print0 | while IFS= read -r -d '' file; do
    # Compute relative path from target_dir
    rel_path="${file#$target_dir/}"

    # If the file is exactly the target_dir itself (should not happen with -type f),
    # but guard against it.
    if [ "$rel_path" = "$file" ]; then
        rel_path="$(basename "$file")"
    fi

    skip=0

    # Skip dotfiles and hidden paths anywhere in the tree
    case "$rel_path" in
        .*|*/.*)
            skip=1
            ;;
    esac

    if [ "$skip" -eq 1 ]; then
        continue
    fi

    if [ -f "$ignore_file" ]; then
        while IFS= read -r pattern; do
            case "$pattern" in
                ''|'#'*)
                    continue
                    ;;
            esac

            # Trailing '/' means the pattern names a directory to be
            # ignored together with every file underneath it.
            case "$pattern" in
                */)
                    dir_pattern="${pattern%/}"
                    case "$rel_path" in
                        $dir_pattern|$dir_pattern/*)
                            skip=1
                            break
                            ;;
                    esac
                    ;;
                *)
                    case "$rel_path" in
                        $pattern)
                            skip=1
                            break
                            ;;
                    esac
                    ;;
            esac
        done < "$ignore_file"
    fi

    if [ "$skip" -eq 1 ]; then
        continue
    fi

    # Skip binary files
    if ! grep -Iq . "$file"; then
        continue
    fi

    echo "$rel_path"
    # Write the opening tag, the file content, and the closing tag
    {
        echo "<file $rel_path>"
        cat "$file"
        echo "</file>"
    } >> "$output_file"
done

echo "All files concatenated into $output_file"
