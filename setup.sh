#!/bin/bash
set -euo pipefail

echo "=== live-stm32 starter kit setup ==="
echo "Modules: K_MIND + K_TOOLS + K_STM32_MCP"

# Init git if needed
if [ ! -d .git ]; then
    git init
    git config core.longpaths true
    echo "Git initialized with core.longpaths=true"
fi

# Make hook executable
chmod +x .claude/hooks/session-start.sh

# Install Python deps
echo "Installing Python dependencies..."
pip3 install -q mcp pygdbmi cmsis-svd 2>/dev/null || \
    pip install -q mcp pygdbmi cmsis-svd 2>/dev/null || \
    echo "WARNING: Could not install Python deps. Install manually: pip install mcp pygdbmi cmsis-svd"

# Init K_MIND session
python3 Knowledge/K_MIND/scripts/session_init.py --session-id "setup-$(date +%s)" 2>/dev/null || true

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit CLAUDE.md — fill in your MCU, pins, build system at the bottom"
echo "  2. Add your SVD file to Knowledge/K_STM32_MCP/svd/"
echo "  3. Edit Knowledge/K_STM32_MCP/mcp/config.json — set target MCU and GDB port"
echo "  4. Run: claude"
echo ""
echo "Available Knowledge commands (once in claude):"
echo "  /know        — Full command reference"
echo "  /mind-context — Load mindmap and context"
echo "  /status      — Session status"
echo "  /test        — Run tests"
