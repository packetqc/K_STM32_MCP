# Methodology — BAT Script Discovery

## Purpose
Discover and catalog available .bat scripts in the STM32 project for build, flash, and utility operations.

## Steps

1. **Scan** — Walk project `scripts/` directory for .bat files
2. **Classify** — Identify purpose (build, flash, clean, test) from filename and content
3. **Register** — Make scripts available as MCP tools via `run_bat` / `list_bat`
4. **Execute** — Run via `cmd.exe /c` for WSL-to-Windows interop
