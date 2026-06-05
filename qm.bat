@echo off
REM ===========================================================================
REM  LCHQMDriver launcher (Windows)
REM  Usage:  qm.bat start   -> launch the QUAlibrate server (default)
REM          qm.bat setup   -> run the interactive QUAlibrate configuration
REM          double-click   -> same as "start"
REM ===========================================================================

REM --- Edit this to target a different conda environment -----------------------
set "ENV_NAME=LCHQM"
REM ----------------------------------------------------------------------------

REM Run from the folder this script lives in (so relative config paths resolve)
cd /d %~dp0

REM Default action is "start" when no argument / double-clicked
set "CMD=%~1"
if "%CMD%"=="" set "CMD=start"

REM Locate conda's activate.bat (miniconda3, then anaconda3)
set "ACTIVATE_PATH=%USERPROFILE%\miniconda3\Scripts\activate.bat"
if not exist "%ACTIVATE_PATH%" set "ACTIVATE_PATH=%USERPROFILE%\anaconda3\Scripts\activate.bat"
if not exist "%ACTIVATE_PATH%" (
    echo [ERROR] Could not find conda activate.bat under:
    echo         %USERPROFILE%\miniconda3\Scripts\activate.bat
    echo         %USERPROFILE%\anaconda3\Scripts\activate.bat
    echo Edit ACTIVATE_PATH in this script to point at your conda installation.
    pause
    exit /b 1
)

echo Activating conda environment "%ENV_NAME%" ...
CALL "%ACTIVATE_PATH%" %ENV_NAME%

if /I "%CMD%"=="setup" (
    setup-qualibrate-config
) else if /I "%CMD%"=="start" (
    qualibrate start
) else (
    echo [ERROR] Unknown command "%CMD%".
    echo Usage: qm.bat [start^|setup]
)

REM Keep the window open so output / errors stay visible after a double-click
pause
