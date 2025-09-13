@echo off
REM Change directory to the one where the batch file was launched
cd /d %~dp0

REM Define variables
set "ENV_NAME=ASQMDriver"
set "ACTIVATE_PATH=%USERPROFILE%\miniconda3\Scripts\activate.bat"
REM anaconda3 or miniconda3

REM Open Anaconda Prompt, activate the environment, and run the command
echo Open conda environment from "%ACTIVATE_PATH%"
CALL "%ACTIVATE_PATH%" %ENV_NAME%

REM Run the Configuration Script

setup-qualibrate-config


REM Keep the window open so you can see any output
pause
