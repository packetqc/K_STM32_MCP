# K_STM32_MCP — STM32 Live Debug Module Instructions

## Overview

This module provides MCP server tools for live STM32 debugging. Claude uses these tools to read/write hardware registers, execute GDB commands, and run BAT build/flash scripts — all through the Model Context Protocol.

## MCP Server

The server runs as a stdio MCP transport, launched by Claude Code via `.mcp.json`:

```json
{
  "mcpServers": {
    "stm32": {
      "command": "python3",
      "args": ["Knowledge/K_STM32_MCP/mcp/server.py"],
      "cwd": "."
    }
  }
}
```

## Tool Layers

### Layer 1: Raw GDB
- `gdb_command(cmd)` — Execute any GDB/MI command directly
- Returns raw GDB/MI response

### Layer 2: High-Level (SVD-Aware)
- `read_register(peripheral, register)` — Read a named peripheral register
- `write_register(peripheral, register, value)` — Write to a named register
- `read_memory(address, length)` — Read raw memory region
- `flash_verify(address, expected)` — Verify flash content

### Layer 3: BAT Scripts
- `list_bat()` — List available .bat scripts with descriptions
- `run_bat(script, args)` — Execute a .bat script via cmd.exe /c

## GDB Connection

- Transport: GDB/MI via pygdbmi
- Default port: 3333 (OpenOCD)
- Connection config in `mcp/config.json`

## SVD Files

Place SVD files for your target MCU in `svd/`. The server auto-discovers them and uses them for named register access.

## Conventions

- Always verify GDB connection before operations
- SVD register names are case-insensitive
- BAT scripts execute via WSL-to-Windows interop (cmd.exe /c)
- All tool responses include raw values and human-readable descriptions
