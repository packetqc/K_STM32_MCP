# K_STM32_MCP — STM32 Live Debug Module

MCP server for live STM32 debugging via Claude Code. Provides GDB/MI integration, SVD-aware register access, and BAT script execution through the Model Context Protocol.

## Structure

```
K_STM32_MCP/
+-- CLAUDE.md            # Module instructions (tool usage, GDB protocols, BAT conventions)
+-- mcp/                  # MCP server component
|   +-- server.py         # Entry point (stdio transport)
|   +-- requirements.txt  # mcp, pygdbmi, cmsis-svd
|   +-- config.json       # Target MCU, GDB port, project paths
|   +-- tools/            # 3 tool layer implementations
+-- svd/                  # SVD files for target MCU
+-- gdb/                  # GDB scripts, .gdbinit
+-- scripts/              # Automation and discovery helpers
+-- methodology/          # Debug session, flash, BAT discovery guides
+-- conventions/          # Tool conventions, routing
+-- behaviors/            # Tool behavioral directives
+-- constraints/          # Hardware limits, GDB constraints
+-- architecture/         # MCP server architecture refs
+-- work/                 # Debug work item tracking
+-- mind/                 # K_STM32_MCP mindmap subtree
```

## Integration

- Sessions and core mindmap stay centralized in K_MIND
- Domain-specific conventions, methodology, and work tracked here
- MCP server discovered via `.mcp.json` at project root
- SVD files provide named peripheral/register access
- GDB connects via OpenOCD to ST-Link hardware

## Tool Layers

| Layer | Tools | Purpose |
|-------|-------|---------|
| Raw GDB | `gdb_command` | Direct GDB/MI commands |
| High-level | `read_register`, `write_register`, `read_memory`, `flash_verify` | SVD-aware operations |
| BAT scripts | `run_bat`, `list_bat` | Windows build/flash script execution |

---
*Part of the Knowledge 2.0 multi-module architecture*
