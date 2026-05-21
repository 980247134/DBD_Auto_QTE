@echo off
cd /d "%~dp0"

set "PYTHON=%cd%\python\python.exe"
set "SCRIPT=%cd%\w7b.py"

if not exist "%PYTHON%" (
    echo [ERROR] Python not found: %PYTHON%
    echo Please run setup.bat first
    echo.
    pause
    exit /b 1
)

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting admin privileges...
    powershell -Command "Start-Process -FilePath '%PYTHON%' -ArgumentList '%SCRIPT%' -WorkingDirectory '%cd%' -Verb RunAs"
    exit /b
)

"%PYTHON%" "%SCRIPT%"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Program exited with code %errorlevel%
)
pause
