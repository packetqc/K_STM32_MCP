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

:: Log file — always tee to this file
set "LOGFILE=%~dp0build_log.txt"
echo [%date% %time%] Build started: %* > "%LOGFILE%"

:: Parse argument
if "%1"=="" goto :build_all
if "%1"=="fsbl" goto :build_fsbl
if "%1"=="appli" goto :build_appli
if "%1"=="clean" goto :clean_all
if "%1"=="all" goto :build_all
echo Unknown argument: %1
echo Usage: build.bat [all^|fsbl^|appli^|clean]
exit /b 1

:clean_all
echo === Cleaning FSBL === >> "%LOGFILE%" 2>&1
echo === Cleaning FSBL ===
mingw32-make.exe -C gcc -f makefile_fsbl clean >> "%LOGFILE%" 2>&1
echo === Cleaning Appli === >> "%LOGFILE%" 2>&1
echo === Cleaning Appli ===
mingw32-make.exe -C gcc -f makefile_appli clean >> "%LOGFILE%" 2>&1
goto :eof

:build_fsbl
echo === Building FSBL ===
echo === Building FSBL === >> "%LOGFILE%"
mingw32-make.exe -C gcc -f makefile_fsbl all >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo FSBL BUILD FAILED >> "%LOGFILE%"
    echo FSBL BUILD FAILED
    exit /b 1
)
echo === FSBL Build Complete === >> "%LOGFILE%"
echo === FSBL Build Complete ===
goto :eof

:build_appli
echo === Building Appli ===
echo === Building Appli === >> "%LOGFILE%"
mingw32-make.exe -C gcc -f makefile_appli all >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo APPLI BUILD FAILED >> "%LOGFILE%"
    echo APPLI BUILD FAILED
    exit /b 1
)
echo === Appli Build Complete === >> "%LOGFILE%"
echo === Appli Build Complete ===
goto :eof

:build_all
call :build_fsbl
if errorlevel 1 exit /b 1
call :build_appli
if errorlevel 1 exit /b 1
echo.
echo === All builds complete === >> "%LOGFILE%"
echo === All builds complete ===
echo FSBL:   FSBL\TouchGFX\build\bin\target.bin >> "%LOGFILE%"
echo Appli:  Appli\TouchGFX\build\bin\target.hex >> "%LOGFILE%"
echo FSBL:   FSBL\TouchGFX\build\bin\target.bin
echo Appli:  Appli\TouchGFX\build\bin\target.hex
echo         Appli\TouchGFX\build\bin\intflash.bin
echo         Appli\TouchGFX\build\bin\assets.hex
echo [%date% %time%] Build finished >> "%LOGFILE%"
