---
name: flash
description: "Build, sign, and flash STM32N6570-DK firmware. Checks if build is needed, builds FSBL+Appli via gcc/Makefile with TouchGFX toolchain, then runs flash BAT scripts."
user_invocable: true
---

# /flash -- Build and Flash STM32N6570-DK

Builds FSBL + Appli via gcc/Makefile (ARM GCC from CubeIDE + TouchGFX env), copies outputs to CubeIDE paths, signs, and flashes to the STM32N6570-DK board.

## Usage

```
/flash              -- build if needed + flash all
/flash build        -- build only, no flash
/flash load         -- flash only (skip build, fail if no binaries)
/flash clean        -- clean build outputs, then build + flash
```

## Build & Flash Scripts

Two BAT files handle the pipeline — they set PATH to include ARM GCC, Ruby, and mingw32-make:
- `build.bat [all|fsbl|appli|clean]` — builds via gcc/Makefile, logs to `build_log.txt`
- `flash.bat [build|load|clean]` — builds + copies outputs + signs + flashes

## Constants

```
BUILD_SCRIPT = build.bat
FLASH_SCRIPT = flash.bat
LOG_FILE = build_log.txt

FSBL_BIN = FSBL/TouchGFX/build/bin/target.bin
APPLI_BIN = Appli/TouchGFX/build/bin/intflash.bin
APPLI_HEX = Appli/TouchGFX/build/bin/target.hex
ASSETS_HEX = Appli/TouchGFX/build/bin/assets.hex
```

## Mandatory Procedure

### Step 1 -- Parse arguments

Parse the user's `/flash` invocation:
- No args or empty -> mode = `full` (build + flash)
- `build` -> mode = `build` (build only)
- `load` -> mode = `load` (flash only)
- `clean` -> mode = `clean` (clean + build + flash)

### Step 2 -- Run the appropriate BAT script via PowerShell

**CRITICAL: Always use PowerShell to run BAT files from bash** — `cmd.exe /c` does not pipe stdout back to the bash shell. Use this pattern:

```bash
powershell.exe -NoProfile -Command "& { Set-Location 'D:\STM32N6\CLAUDE_MCP_STM32'; .\flash.bat <arg> 2>&1 }"
```

Or for build-only:
```bash
powershell.exe -NoProfile -Command "& { Set-Location 'D:\STM32N6\CLAUDE_MCP_STM32'; .\build.bat <arg> 2>&1 }"
```

**Timeout**: First build is long (~2-5 min for Appli with TouchGFX assets). Set timeout to 600000 (10 min).

**Background execution**: For long builds, run in background and monitor `build_log.txt`:
```bash
# Start build in background
powershell.exe -NoProfile -Command "& { Set-Location 'D:\STM32N6\CLAUDE_MCP_STM32'; .\build.bat all 2>&1 }" &

# Monitor log
tail -f build_log.txt
```

### Step 3 -- Check build log for errors

After build completes, read `build_log.txt`:
```bash
cat build_log.txt | tail -40
```

Look for:
- `BUILD FAILED` -> report error, show relevant compiler output
- `Build Complete` -> success
- Compiler errors (`error:` lines) -> can fix source code and rebuild
- Linker errors (`undefined reference`) -> report dependency issues

### Step 4 -- Verify outputs

```bash
ls -la FSBL/TouchGFX/build/bin/target.bin Appli/TouchGFX/build/bin/intflash.bin Appli/TouchGFX/build/bin/assets.hex 2>&1
```

### Step 5 -- Report

Output a summary:

```
| Component | Status | Size     |
|-----------|--------|----------|
| FSBL      | OK     | 32.2 KB  |
| Appli     | OK     | 341.3 KB |
| Assets    | OK     | 1.3 KB   |
| Flash     | OK     | (signed) |
```

## Error Handling

| Error | Action |
|-------|--------|
| Build fails | Show last 30 lines of build_log.txt. Look for `error:` lines with file:line. Fix and rebuild. |
| `ruby` not found | Ruby is at `C:\TouchGFX\4.26.1\env\MinGW\msys\1.0\Ruby30-x64\bin` — check build.bat PATH |
| `arm-none-eabi-gcc` not found | Toolchain at `C:\ST\STM32CubeIDE_1.19.0\STM32CubeIDE\plugins\...\tools\bin` — check build.bat PATH |
| Flash fails (no board) | STM32_Programmer_CLI error. Check USB connection, ST-Link driver. |
| Assets empty (1.3 KB) | Normal for default TouchGFX project with no custom assets. |

## Build System Details

- **Toolchain**: ARM GCC 14.3 from STM32CubeIDE 1.19.0
- **Build**: gcc/Makefile system (makefile_fsbl + makefile_appli)
- **Assets**: TouchGFX imageconvert + Ruby textconvert + fontconvert
- **Make**: mingw32-make from TouchGFX 4.26.1 env
- **Output**: gcc Makefiles output to `*/TouchGFX/build/bin/`
- **Flash scripts**: Expect files at `STM32CubeIDE/*/Debug/` -> `flash.bat` copies them there
- **Signing**: STM32_SigningTool_CLI signs FSBL and Appli before flashing
- **Flash addresses**: FSBL at 0x70000000, Appli at 0x70100000
