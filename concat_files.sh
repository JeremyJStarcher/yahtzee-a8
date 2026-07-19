#!/usr/bin/env bash

# Usage check
if [ $# -ne 1 ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

target_dir="$1"

# Validate directory
if [ ! -d "$target_dir" ]; then
    echo "Error: '$target_dir' is not a directory" >&2
    exit 1
fi

# Remove trailing slash if present (for clean relative paths)
target_dir="${target_dir%/}"

output_file="/tmp/all.txt"

# Start fresh
> "$output_file" || { echo "Error: cannot write to $output_file" >&2; exit 1; }

# Find all regular files, process them one by one
find "$target_dir" -type f -print0 | while IFS= read -r -d '' file; do
    # Compute relative path from target_dir
    rel_path="${file#$target_dir/}"

    # If the file is exactly the target_dir itself (should not happen with -type f),
    # but guard against it.
    if [ "$rel_path" = "$file" ]; then
        rel_path="$(basename "$file")"
    fi

    # Write the opening tag, the file content, and the closing tag
    {
        echo "<file $rel_path>"
        cat "$file"
        echo "</file>"
    } >> "$output_file"
done

echo "All files concatenated into $output_file"
