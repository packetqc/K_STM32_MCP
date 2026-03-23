#!/bin/bash
set -euo pipefail

# Build live-stm32-starter.tar.gz
# Run from repository root: bash Knowledge/K_STM32_MCP/scripts/build-starter-kit.sh
#
# Package includes:
#   - Full K_MIND (memory engine, scripts, clean sessions)
#   - Full K_TOOLS (testing, visualization, projects, validation, sessions)
#   - Full K_STM32_MCP (MCP server, SVD, GDB, methodologies)
#   - Root CLAUDE.md = actual K_MIND instructions + K_STM32_MCP section appended
#   - .claude/ = hooks + settings + all applicable skills (K_MIND + K_TOOLS + infra)
#   - .mcp.json, modules.json, setup.sh

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BUILD_DIR="/tmp/live-stm32-starter"
OUTPUT="$REPO_ROOT/Knowledge/K_STM32_MCP/dist/live-stm32-starter.tar.gz"

echo "Building live-stm32-starter.tar.gz..."

# Clean
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

###############################################################################
# 1. CLAUDE.md — Real K_MIND instructions + K_STM32_MCP section appended
###############################################################################
if [ -f "$REPO_ROOT/CLAUDE.md" ]; then
    cp "$REPO_ROOT/CLAUDE.md" "$BUILD_DIR/CLAUDE.md"
elif [ -f "$REPO_ROOT/Knowledge/K_MIND/CLAUDE.md" ]; then
    cp "$REPO_ROOT/Knowledge/K_MIND/CLAUDE.md" "$BUILD_DIR/CLAUDE.md"
fi

# Append K_STM32_MCP section
if [ -f "$REPO_ROOT/Knowledge/K_STM32_MCP/CLAUDE.md" ]; then
    echo "" >> "$BUILD_DIR/CLAUDE.md"
    echo "---" >> "$BUILD_DIR/CLAUDE.md"
    echo "" >> "$BUILD_DIR/CLAUDE.md"
    cat "$REPO_ROOT/Knowledge/K_STM32_MCP/CLAUDE.md" >> "$BUILD_DIR/CLAUDE.md"
fi

###############################################################################
# 2. K_MIND — Full module, clean sessions
###############################################################################
mkdir -p "$BUILD_DIR/Knowledge/K_MIND"

# Scripts (no __pycache__)
cp -r "$REPO_ROOT/Knowledge/K_MIND/scripts" "$BUILD_DIR/Knowledge/K_MIND/"
rm -rf "$BUILD_DIR/Knowledge/K_MIND/scripts/__pycache__"

# Methodology
if [ -d "$REPO_ROOT/Knowledge/K_MIND/methodology" ]; then
    cp -r "$REPO_ROOT/Knowledge/K_MIND/methodology" "$BUILD_DIR/Knowledge/K_MIND/"
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

###############################################################################
# 3. K_TOOLS — Full module
###############################################################################
mkdir -p "$BUILD_DIR/Knowledge/K_TOOLS"

# Copy all K_TOOLS contents
# Copy structure (exclude test-reports — project-specific data, not starter kit content)
for item in conventions documentation methodology scripts skills work; do
    if [ -d "$REPO_ROOT/Knowledge/K_TOOLS/$item" ]; then
        cp -r "$REPO_ROOT/Knowledge/K_TOOLS/$item" "$BUILD_DIR/Knowledge/K_TOOLS/"
    fi
done
# Create empty dirs for test artifacts
mkdir -p "$BUILD_DIR/Knowledge/K_TOOLS/test-plans"
mkdir -p "$BUILD_DIR/Knowledge/K_TOOLS/test-reports"

# Clean __pycache__
find "$BUILD_DIR/Knowledge/K_TOOLS" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

###############################################################################
# 4. K_STM32_MCP — Full module
###############################################################################
mkdir -p "$BUILD_DIR/Knowledge/K_STM32_MCP"

# Copy everything except dist/ and scripts/build-starter-kit.sh
for item in CLAUDE.md README.md conventions documentation methodology mind work behaviors constraints architecture; do
    if [ -e "$REPO_ROOT/Knowledge/K_STM32_MCP/$item" ]; then
        cp -r "$REPO_ROOT/Knowledge/K_STM32_MCP/$item" "$BUILD_DIR/Knowledge/K_STM32_MCP/"
    fi
done

# Create empty dirs for svd, gdb, scripts
for dir in svd gdb scripts; do
    mkdir -p "$BUILD_DIR/Knowledge/K_STM32_MCP/$dir"
done

# MCP server placeholder if not yet implemented
if [ ! -f "$REPO_ROOT/Knowledge/K_STM32_MCP/mcp/server.py" ]; then
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
else
    cp -r "$REPO_ROOT/Knowledge/K_STM32_MCP/mcp" "$BUILD_DIR/Knowledge/K_STM32_MCP/"
fi

###############################################################################
# 5. modules.json
###############################################################################
cat > "$BUILD_DIR/Knowledge/modules.json" << 'MODEOF'
{
  "description": "Knowledge module registry",
  "modules": [
    {
      "id": "K_MIND",
      "name": "Knowledge Mind",
      "description": "Core memory system — mindmap, session management, near/far memory, scripts",
      "status": "active",
      "path": "Knowledge/K_MIND",
      "has": ["mind", "sessions", "architecture", "constraints", "conventions", "work", "documentation", "scripts"]
    },
    {
      "id": "K_TOOLS",
      "name": "Knowledge Tools",
      "description": "Operational utilities — testing, visualization, validation, projects, sessions, help system",
      "status": "active",
      "path": "Knowledge/K_TOOLS",
      "has": ["conventions", "documentation", "methodology", "scripts", "skills", "test-plans", "test-reports", "work"]
    },
    {
      "id": "K_STM32_MCP",
      "name": "STM32 Live Debug",
      "description": "MCP server for live STM32 debugging — GDB/MI integration, SVD register access, BAT script execution",
      "status": "active",
      "path": "Knowledge/K_STM32_MCP",
      "has": ["architecture", "behaviors", "constraints", "conventions", "documentation", "methodology", "mind", "mcp", "scripts", "svd", "gdb", "work"]
    }
  ]
}
MODEOF

###############################################################################
# 6. .claude/ — hooks + settings + ALL applicable skills
###############################################################################
mkdir -p "$BUILD_DIR/.claude/hooks"

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

# ALL applicable skills (K_MIND core + K_TOOLS + Generic/Infra)
# Excludes only K_DOCS-specific: pub, pub-export, docs-create, doc-review, webcard, generate-og
EXCLUDE_SKILLS="pub pub-export docs-create doc-review webcard generate-og"

for skill_dir in "$REPO_ROOT/.claude/skills"/*/; do
    skill_name=$(basename "$skill_dir")

    # Skip K_DOCS-specific skills
    skip=false
    for excluded in $EXCLUDE_SKILLS; do
        if [ "$skill_name" = "$excluded" ]; then
            skip=true
            break
        fi
    done

    if [ "$skip" = false ] && [ -f "$skill_dir/SKILL.md" ]; then
        cp -r "$skill_dir" "$BUILD_DIR/.claude/skills/"
    fi
done

###############################################################################
# 7. .mcp.json
###############################################################################
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

###############################################################################
# 8. setup.sh
###############################################################################
cat > "$BUILD_DIR/setup.sh" << 'SETUPEOF'
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
SETUPEOF
chmod +x "$BUILD_DIR/setup.sh"

###############################################################################
# 9. Package
###############################################################################
mkdir -p "$(dirname "$OUTPUT")"
cd /tmp
tar czf "$OUTPUT" -C "$BUILD_DIR" .

# Stats
FILE_COUNT=$(find "$BUILD_DIR" -type f | wc -l)
DIR_COUNT=$(find "$BUILD_DIR" -type d | wc -l)
SIZE=$(du -sh "$OUTPUT" | cut -f1)

echo ""
echo "Built: $OUTPUT"
echo "Files: $FILE_COUNT  Dirs: $DIR_COUNT"
echo "Size: $SIZE"
echo ""
echo "Modules included:"
echo "  - K_MIND   (memory engine, scripts, clean sessions)"
echo "  - K_TOOLS  (testing, visualization, projects, validation)"
echo "  - K_STM32_MCP (MCP server, SVD, GDB, methodologies)"
echo ""
echo "Skills: $(ls -d "$BUILD_DIR/.claude/skills"/*/ 2>/dev/null | wc -l) included"
echo "Excluded (K_DOCS-only): $EXCLUDE_SKILLS"

# Cleanup
rm -rf "$BUILD_DIR"
