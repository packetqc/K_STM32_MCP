#!/bin/bash
# Install repo-level auto-memory files to Claude Code's project memory
# Source: .claude/memory/ (in repo) or Knowledge/K_MIND/.claude/memory/ (imported)
# Target: /root/.claude/projects/<project-path>/memory/ (Claude Code system)

set -euo pipefail

# Detect K_MIND location: standalone or imported
if [ -d "$CLAUDE_PROJECT_DIR/Knowledge/K_MIND/scripts" ]; then
    REPO_MEMORY="$CLAUDE_PROJECT_DIR/Knowledge/K_MIND/.claude/memory"
else
    REPO_MEMORY="$CLAUDE_PROJECT_DIR/.claude/memory"
fi
# Convert project dir to Claude Code's path format (/ becomes -)
PROJECT_PATH=$(echo "$CLAUDE_PROJECT_DIR" | sed 's|^/||; s|/|-|g')
TARGET_MEMORY="/root/.claude/projects/-${PROJECT_PATH}/memory"

# Skip if no repo memory files exist
if [ ! -d "$REPO_MEMORY" ]; then
    exit 0
fi

# Create target directory
mkdir -p "$TARGET_MEMORY"

# Copy each memory file if newer or missing
for src in "$REPO_MEMORY"/*.md; do
    [ -f "$src" ] || continue
    filename=$(basename "$src")
    target="$TARGET_MEMORY/$filename"
    if [ ! -f "$target" ] || [ "$src" -nt "$target" ]; then
        cp "$src" "$target"
    fi
done
