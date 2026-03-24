# Methodology — Flash and Verify

## Purpose
Flash firmware to STM32 target and verify successful programming.

## Steps

1. **Build** — Execute build BAT script to compile firmware
2. **Flash** — Execute flash BAT script (OpenOCD or ST-Link CLI)
3. **Verify** — Read known memory locations to confirm flash content
4. **Reset** — Reset target and verify startup behavior
