@echo off
chcp 65001 >nul
cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在请求管理员权限启动 QTE Auto Tool...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -WorkingDirectory '%~dp0' -Verb RunAs"
    exit /b
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "main.py"
) else (
    python "main.py"
)

pause
