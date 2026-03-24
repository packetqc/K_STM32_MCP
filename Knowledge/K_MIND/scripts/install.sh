#!/bin/bash
# K_MIND Module Installer — Create a new Knowledge module alongside K_MIND
# Usage: bash Knowledge/K_MIND/scripts/install.sh <MODULE_NAME>
# Example: bash Knowledge/K_MIND/scripts/install.sh K_DOCS
#
# Run from the project root (where CLAUDE.md and .claude/ live).
# Creates Knowledge/<MODULE_NAME>/ with a basic module structure.

set -euo pipefail

MODULE_NAME="${1:-}"

if [ -z "$MODULE_NAME" ]; then
    echo "Usage: bash Knowledge/K_MIND/scripts/install.sh <MODULE_NAME>"
    echo "Example: bash Knowledge/K_MIND/scripts/install.sh K_DOCS"
    exit 1
fi

# Verify we're at project root (Knowledge/K_MIND must exist)
if [ ! -d "Knowledge/K_MIND/scripts" ]; then
    echo "Error: Knowledge/K_MIND/scripts not found."
    echo "Run this from the project root."
    exit 1
fi

MODULE_DIR="Knowledge/$MODULE_NAME"

if [ -d "$MODULE_DIR" ]; then
    echo "Module $MODULE_NAME already exists at $MODULE_DIR"
    exit 0
fi

echo "Creating module: $MODULE_NAME"

# --- Create module directory structure ---
mkdir -p "$MODULE_DIR"
echo "  Created $MODULE_DIR/"

# --- Create docs/ at project root (documentation convention) ---
if [ ! -d "docs" ]; then
    mkdir -p "docs"
    touch "docs/.gitkeep"
    echo "  Created docs/ (documentation root)"
fi

echo ""
echo "Module $MODULE_NAME created at $MODULE_DIR/"
echo "K_MIND is ready — launch 'claude' to start working."
