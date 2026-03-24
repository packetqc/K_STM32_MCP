# Methodology — GDB Debug Session

## Purpose
Establish a live GDB connection to an STM32 target via OpenOCD and perform register/memory inspection.

## Prerequisites
- OpenOCD running with ST-Link connected
- GDB server listening on configured port (default: 3333)
- SVD file present for target MCU

## Steps

1. **Connect** — MCP server establishes GDB/MI connection via pygdbmi
2. **Load SVD** — Parse SVD file for peripheral/register definitions
3. **Read/Write** — Use SVD-aware tools to access named registers
4. **Inspect** — Read memory regions, check peripheral states
5. **Disconnect** — Clean GDB session teardown
