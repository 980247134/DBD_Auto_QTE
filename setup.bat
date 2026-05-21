@echo off
set "PYTHON_VERSION=3.12.9"
set "PYTHON_EMBED=python-%PYTHON_VERSION%-embed-amd64"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_EMBED%.zip"
set "GETPIP_URL=https://bootstrap.pypa.io/get-pip.py"
set "ROOT=%~dp0"
set "PYTHON_DIR=%ROOT%python"

echo ============================================
echo   Setup - Embedded Python Environment
echo ============================================
echo.

if not exist "%ROOT%temp" mkdir "%ROOT%temp"

if not exist "%PYTHON_DIR%\python.exe" (
    echo [1/3] Downloading Python %PYTHON_VERSION%...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%ROOT%temp\python-embed.zip'}"
    if errorlevel 1 (
        echo [ERROR] Download failed
        echo URL: %PYTHON_URL%
        pause
        exit /b 1
    )

    echo     Extracting Python...
    mkdir "%PYTHON_DIR%"
    powershell -Command "Expand-Archive -Path '%ROOT%temp\python-embed.zip' -DestinationPath '%PYTHON_DIR%' -Force"
    if errorlevel 1 (
        echo [ERROR] Extraction failed
        pause
        exit /b 1
    )

    del /q "%ROOT%temp\python-embed.zip" 2>nul

    echo     Patching pth file...
    if exist "%PYTHON_DIR%\python312._pth" (
        echo Lib\site-packages>> "%PYTHON_DIR%\python312._pth"
        echo ..>> "%PYTHON_DIR%\python312._pth"
        echo import site>> "%PYTHON_DIR%\python312._pth"
    )

    echo     Downloading get-pip.py...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%GETPIP_URL%' -OutFile '%ROOT%temp\get-pip.py'}"
    if errorlevel 1 (
        echo [ERROR] get-pip.py download failed
        pause
        exit /b 1
    )

    echo     Installing pip...
    "%PYTHON_DIR%\python.exe" "%ROOT%temp\get-pip.py" --no-warn-script-location
    if errorlevel 1 (
        echo [ERROR] pip install failed
        pause
        exit /b 1
    )

    del /q "%ROOT%temp\get-pip.py" 2>nul
) else (
    echo [OK] Python already exists, skipping download
)

echo [2/3] Installing dependencies...
"%PYTHON_DIR%\python.exe" -m pip install -r "%ROOT%requirements.txt" --no-warn-script-location
if errorlevel 1 (
    echo [ERROR] Dependency install failed
    pause
    exit /b 1
)

echo [3/3] Cleanup...
rmdir /s /q "%ROOT%temp" 2>nul

echo.
echo ============================================
echo   Setup complete!
echo   Run run.bat to start the program
echo ============================================
echo.
pause
