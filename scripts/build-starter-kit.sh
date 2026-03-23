#!/bin/bash
set -euo pipefail

# Build live-stm32-starter.tar.gz
# Run from repository root: bash Knowledge/K_STM32_MCP/scripts/build-starter-kit.sh

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BUILD_DIR="/tmp/live-stm32-starter"
OUTPUT="$REPO_ROOT/Knowledge/K_STM32_MCP/dist/live-stm32-starter.tar.gz"

echo "Building live-stm32-starter.tar.gz..."

# Clean
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# --- K_MIND (full module, clean sessions) ---
mkdir -p "$BUILD_DIR/Knowledge/K_MIND"
cp -r "$REPO_ROOT/Knowledge/K_MIND/scripts" "$BUILD_DIR/Knowledge/K_MIND/"
rm -rf "$BUILD_DIR/Knowledge/K_MIND/scripts/__pycache__"
cp -r "$REPO_ROOT/Knowledge/K_MIND/methodology" "$BUILD_DIR/Knowledge/K_MIND/"
# K_MIND's CLAUDE.md lives at repo root in the host project
# For the starter kit, we place it inside the module directory
if [ -f "$REPO_ROOT/Knowledge/K_MIND/CLAUDE.md" ]; then
    cp "$REPO_ROOT/Knowledge/K_MIND/CLAUDE.md" "$BUILD_DIR/Knowledge/K_MIND/"
elif [ -f "$REPO_ROOT/CLAUDE.md" ]; then
    cp "$REPO_ROOT/CLAUDE.md" "$BUILD_DIR/Knowledge/K_MIND/"
fi

# Skeleton mind
mkdir -p "$BUILD_DIR/Knowledge/K_MIND/mind"
cat > "$BUILD_DIR/Knowledge/K_MIND/mind/mind_memory.md" << 'MINDEOF'
# Project Mindmap

```mermaid
mindmap
  root((Project))
    work
      en cours
        initial setup
    conventions
    constraints
    documentation
```
MINDEOF

# Empty sessions
mkdir -p "$BUILD_DIR/Knowledge/K_MIND/sessions/archives"
echo '{"messages":[]}' > "$BUILD_DIR/Knowledge/K_MIND/sessions/far_memory.json"
echo '{"pinned":[],"wip_context":{"active_branch":"","work_items":[],"decision_log":[],"activity_chain":[]},"summaries":[]}' > "$BUILD_DIR/Knowledge/K_MIND/sessions/near_memory.json"

# Empty domain JSONs
for dir in conventions behaviors architecture constraints work documentation; do
    mkdir -p "$BUILD_DIR/Knowledge/K_MIND/$dir"
done
echo '{"module":"K_MIND","conventions":[]}' > "$BUILD_DIR/Knowledge/K_MIND/conventions/conventions.json"
echo '{"module":"K_MIND","routing":[]}' > "$BUILD_DIR/Knowledge/K_MIND/conventions/routing.json"
echo '{"module":"K_MIND","behaviors":{}}' > "$BUILD_DIR/Knowledge/K_MIND/behaviors/behaviors.json"
echo '{"module":"K_MIND","architecture":{}}' > "$BUILD_DIR/Knowledge/K_MIND/architecture/architecture.json"
echo '{"module":"K_MIND","constraints":[]}' > "$BUILD_DIR/Knowledge/K_MIND/constraints/constraints.json"
echo '{"module":"K_MIND","work":[]}' > "$BUILD_DIR/Knowledge/K_MIND/work/work.json"
echo '{"domain":"documentation","module":"K_MIND","references":[],"external_files":[]}' > "$BUILD_DIR/Knowledge/K_MIND/documentation/documentation.json"

# Depth config
echo '{}' > "$BUILD_DIR/Knowledge/K_MIND/depth_config.json"

# --- K_STM32_MCP (full module) ---
mkdir -p "$BUILD_DIR/Knowledge/K_STM32_MCP"
# Copy everything except dist/
for item in CLAUDE.md README.md conventions documentation methodology mind work mcp svd gdb scripts behaviors constraints architecture; do
    if [ -e "$REPO_ROOT/Knowledge/K_STM32_MCP/$item" ]; then
        cp -r "$REPO_ROOT/Knowledge/K_STM32_MCP/$item" "$BUILD_DIR/Knowledge/K_STM32_MCP/"
    else
        mkdir -p "$BUILD_DIR/Knowledge/K_STM32_MCP/$item"
    fi
done

# MCP server placeholder if not yet implemented
if [ ! -f "$BUILD_DIR/Knowledge/K_STM32_MCP/mcp/server.py" ]; then
    mkdir -p "$BUILD_DIR/Knowledge/K_STM32_MCP/mcp/tools"
    cat > "$BUILD_DIR/Knowledge/K_STM32_MCP/mcp/server.py" << 'SERVEREOF'
#!/usr/bin/env python3
"""K_STM32_MCP — MCP server for live STM32 debugging.

Placeholder — implement tool handlers in tools/ directory.
"""
import sys

def main():
    print("K_STM32_MCP server not yet implemented", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
SERVEREOF
    cat > "$BUILD_DIR/Knowledge/K_STM32_MCP/mcp/requirements.txt" << 'REQEOF'
mcp>=1.0.0
pygdbmi>=0.11.0.0
cmsis-svd>=0.4
REQEOF
    cat > "$BUILD_DIR/Knowledge/K_STM32_MCP/mcp/config.json" << 'CFGEOF'
{
  "target_mcu": "STM32F4xx",
  "gdb_port": 3333,
  "gdb_host": "localhost",
  "svd_path": "Knowledge/K_STM32_MCP/svd",
  "bat_scripts_dir": "scripts"
}
CFGEOF
fi

# --- modules.json ---
cat > "$BUILD_DIR/Knowledge/modules.json" << 'MODEOF'
{
  "description": "Knowledge module registry",
  "modules": [
    {
      "id": "K_MIND",
      "name": "Knowledge Mind",
      "description": "Core memory system — mindmap, session management, near/far memory, scripts",
      "status": "active",
      "imported": true,
      "upstream": "packetqc/k-mind",
      "path": "Knowledge/K_MIND",
      "has": ["mind", "sessions", "architecture", "constraints", "conventions", "work", "documentation", "scripts"]
    },
    {
      "id": "K_STM32_MCP",
      "name": "STM32 Live Debug",
      "description": "MCP server for live STM32 debugging — GDB/MI integration, SVD register access, BAT script execution",
      "status": "active",
      "imported": true,
      "upstream": "packetqc/k-stm32-mcp",
      "path": "Knowledge/K_STM32_MCP",
      "has": ["architecture", "behaviors", "constraints", "conventions", "documentation", "methodology", "mind", "mcp", "scripts", "svd", "gdb", "work"]
    }
  ]
}
MODEOF

# --- .claude/ (config + hook + 12 lean skills) ---
mkdir -p "$BUILD_DIR/.claude/hooks"
mkdir -p "$BUILD_DIR/.claude/skills"

# settings.json
cat > "$BUILD_DIR/.claude/settings.json" << 'SETEOF'
{
    "$schema": "https://json.schemastore.org/claude-code-settings.json",
    "hooks": {
        "SessionStart": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.sh"
                    }
                ]
            }
        ]
    }
}
SETEOF

# session-start hook
cp "$REPO_ROOT/.claude/hooks/session-start.sh" "$BUILD_DIR/.claude/hooks/"
chmod +x "$BUILD_DIR/.claude/hooks/session-start.sh"

# 12 lean skills
LEAN_SKILLS="mind-context mind-stats recall remember status github elevate save-session checkpoint refresh resume know"
for skill in $LEAN_SKILLS; do
    if [ -d "$REPO_ROOT/.claude/skills/$skill" ]; then
        cp -r "$REPO_ROOT/.claude/skills/$skill" "$BUILD_DIR/.claude/skills/"
    fi
done

# --- .mcp.json ---
cat > "$BUILD_DIR/.mcp.json" << 'MCPEOF'
{
  "mcpServers": {
    "stm32": {
      "command": "python3",
      "args": ["Knowledge/K_STM32_MCP/mcp/server.py"],
      "cwd": "."
    }
  }
}
MCPEOF

# --- Root CLAUDE.md template ---
cat > "$BUILD_DIR/CLAUDE.md" << 'CLAUDEEOF'
# Project Instructions

## Development — STM32 Configuration

- **Target MCU**: (e.g., STM32F411RE)
- **Clock**: (e.g., HSE 8MHz, PLL 100MHz)
- **Debug interface**: ST-Link V2 via OpenOCD
- **GDB port**: 3333
- **Build system**: (e.g., STM32CubeIDE, Makefile, CMake)
- **Flash procedure**: (e.g., `scripts/flash.bat`)

### Pin Assignments

| Pin | Function | Notes |
|-----|----------|-------|
| PA5 | LED | Onboard LED |

### Coding Standards

- (your conventions here)

## Project — Firmware Description

- **Purpose**: (what the firmware does)
- **Test procedures**: (how to verify)
- **Acceptance criteria**: (what "done" looks like)
CLAUDEEOF

# --- setup.sh ---
cat > "$BUILD_DIR/setup.sh" << 'SETUPEOF'
#!/bin/bash
set -euo pipefail

echo "=== live-stm32 starter kit setup ==="

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
echo "  1. Edit CLAUDE.md — fill in your MCU, pins, build system"
echo "  2. Add your SVD file to Knowledge/K_STM32_MCP/svd/"
echo "  3. Edit Knowledge/K_STM32_MCP/mcp/config.json — set target MCU and GDB port"
echo "  4. Run: claude"
SETUPEOF
chmod +x "$BUILD_DIR/setup.sh"

# --- Package ---
mkdir -p "$(dirname "$OUTPUT")"
cd /tmp
tar czf "$OUTPUT" -C "$BUILD_DIR" .

# Stats
FILE_COUNT=$(find "$BUILD_DIR" -type f | wc -l)
SIZE=$(du -sh "$OUTPUT" | cut -f1)

echo ""
echo "Built: $OUTPUT"
echo "Files: $FILE_COUNT"
echo "Size: $SIZE"
echo ""

# Cleanup
rm -rf "$BUILD_DIR"
