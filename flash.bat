@echo off
setlocal

:: ARM GCC toolchain from STM32CubeIDE
set "TOOLCHAIN=C:\ST\STM32CubeIDE_1.19.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.14.3.rel1.win32_1.0.100.202602081740\tools\bin"

:: TouchGFX environment (Ruby, make, imageconvert)
set "TOUCHGFX_ENV=C:\TouchGFX\4.26.1\env\MinGW"
set "RUBY_BIN=%TOUCHGFX_ENV%\msys\1.0\Ruby30-x64\bin"
set "MAKE_BIN=%TOUCHGFX_ENV%\bin"

:: Set PATH
set "PATH=%TOOLCHAIN%;%RUBY_BIN%;%MAKE_BIN%;%PATH%"

:: Navigate to project root
cd /d "%~dp0"

:: Log file
set "LOGFILE=%~dp0build_log.txt"
echo [%date% %time%] Flash started: %* > "%LOGFILE%"

:: Flash scripts dir
set "FLASH_DIR=%~dp0Flash scripts\CubeIDE\Debug"

:: Build output locations (gcc/Makefile outputs)
set "FSBL_BIN=FSBL\TouchGFX\build\bin\target.bin"
set "APPLI_BIN=Appli\TouchGFX\build\bin\intflash.bin"
set "APPLI_HEX=Appli\TouchGFX\build\bin\target.hex"
set "ASSETS_HEX=Appli\TouchGFX\build\bin\assets.hex"

:: CubeIDE output locations (where flash scripts expect files)
set "CUBEIDE_FSBL_DIR=STM32CubeIDE\FSBL\Debug"
set "CUBEIDE_APPLI_DIR=STM32CubeIDE\Appli\Debug"

:: Parse argument
if "%1"=="" goto :full
if "%1"=="build" goto :build_only
if "%1"=="load" goto :load_only
if "%1"=="clean" goto :clean_build_flash
echo Unknown argument: %1
echo Usage: flash.bat [build^|load^|clean]
exit /b 1

:full
echo === Full: Build + Flash ===
echo === Full: Build + Flash === >> "%LOGFILE%"

:: Check if build is needed
if exist "%FSBL_BIN%" if exist "%APPLI_HEX%" (
    echo Build artifacts exist. Rebuilding anyway for safety...
    echo Build artifacts exist. Rebuilding anyway for safety... >> "%LOGFILE%"
)

call :do_build
if errorlevel 1 exit /b 1
call :do_copy
call :do_flash
goto :eof

:build_only
echo === Build Only ===
call :do_build
if errorlevel 1 exit /b 1
call :do_copy
echo === Build complete, not flashing ===
goto :eof

:load_only
echo === Load Only (no build) ===
if not exist "%CUBEIDE_FSBL_DIR%\STM32N6570-DK_FSBL.bin" (
    echo ERROR: No FSBL binary found. Run "flash.bat build" first.
    exit /b 1
)
if not exist "%CUBEIDE_APPLI_DIR%\STM32N6570-DK_Appli.bin" (
    echo ERROR: No Appli binary found. Run "flash.bat build" first.
    exit /b 1
)
call :do_flash
goto :eof

:clean_build_flash
echo === Clean Build + Flash ===
call "%~dp0build.bat" clean
call :do_build
if errorlevel 1 exit /b 1
call :do_copy
call :do_flash
goto :eof

:: ============================================================
:: Internal subroutines
:: ============================================================

:do_build
echo --- Building FSBL ---
echo --- Building FSBL --- >> "%LOGFILE%"
mingw32-make.exe -C gcc -f makefile_fsbl all >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo FSBL BUILD FAILED - see build_log.txt
    echo FSBL BUILD FAILED >> "%LOGFILE%"
    exit /b 1
)
echo FSBL OK >> "%LOGFILE%"

echo --- Building Appli ---
echo --- Building Appli --- >> "%LOGFILE%"
mingw32-make.exe -C gcc -f makefile_appli all >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo APPLI BUILD FAILED - see build_log.txt
    echo APPLI BUILD FAILED >> "%LOGFILE%"
    exit /b 1
)
echo Appli OK >> "%LOGFILE%"
echo --- Build Complete ---
goto :eof

:do_copy
:: Copy gcc build outputs to where the CubeIDE flash scripts expect them
echo --- Copying build outputs to CubeIDE paths ---
echo --- Copying build outputs --- >> "%LOGFILE%"

if not exist "%CUBEIDE_FSBL_DIR%" mkdir "%CUBEIDE_FSBL_DIR%"
if not exist "%CUBEIDE_APPLI_DIR%" mkdir "%CUBEIDE_APPLI_DIR%"

:: FSBL: target.bin -> STM32N6570-DK_FSBL.bin
copy /y "%FSBL_BIN%" "%CUBEIDE_FSBL_DIR%\STM32N6570-DK_FSBL.bin" >> "%LOGFILE%" 2>&1

:: Appli: intflash.bin -> STM32N6570-DK_Appli.bin (code only, no external flash sections)
copy /y "%APPLI_BIN%" "%CUBEIDE_APPLI_DIR%\STM32N6570-DK_Appli.bin" >> "%LOGFILE%" 2>&1

:: Assets: assets.hex -> STM32N6570-DK_Appli_assets.hex
copy /y "%ASSETS_HEX%" "%CUBEIDE_APPLI_DIR%\STM32N6570-DK_Appli_assets.hex" >> "%LOGFILE%" 2>&1

echo Copies complete >> "%LOGFILE%"
goto :eof

:do_flash
echo --- Signing and Flashing ---
echo --- Signing and Flashing --- >> "%LOGFILE%"

echo [FSBL Sign+Load] >> "%LOGFILE%"
call "%FLASH_DIR%\SignAndLoad_FSBL.bat" < nul >> "%LOGFILE%" 2>&1
echo FSBL flash exit code: %errorlevel% >> "%LOGFILE%"

echo [Appli Sign+Load] >> "%LOGFILE%"
call "%FLASH_DIR%\SignAndLoad_App.bat" < nul >> "%LOGFILE%" 2>&1
echo Appli flash exit code: %errorlevel% >> "%LOGFILE%"

echo [Assets Load] >> "%LOGFILE%"
call "%FLASH_DIR%\LoadAssets.bat" < nul >> "%LOGFILE%" 2>&1
echo Assets flash exit code: %errorlevel% >> "%LOGFILE%"

echo --- Flash Complete ---
echo [%date% %time%] Flash finished >> "%LOGFILE%"
goto :eof
