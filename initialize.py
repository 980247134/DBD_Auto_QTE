#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
from pathlib import Path

def get_project_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


PROJECT_DIR = get_project_dir()
VENV_DIR = PROJECT_DIR / ".venv"
REQUIREMENTS = PROJECT_DIR / "requirements.txt"
RUN_BAT = PROJECT_DIR / "run_qte.bat"

REQUIRED_MODULES = {
    "cv2": "opencv-python",
    "mss": "mss",
    "pydirectinput": "pydirectinput",
    "numpy": "numpy",
    "PIL": "Pillow",
    "serial": "pyserial",
}


def pause(exit_code: int = 0):
    input("\n按 Enter 退出...")
    raise SystemExit(exit_code)


def run(cmd, cwd=PROJECT_DIR):
    print(f"\n> {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        print(f"\n命令执行失败，退出码: {result.returncode}")
        pause(result.returncode)


def venv_python() -> Path:
    return VENV_DIR / "Scripts" / "python.exe"


def find_system_python():
    if not getattr(sys, "frozen", False):
        return [sys.executable]

    candidates = []
    py_launcher = shutil.which("py")
    if py_launcher:
        candidates.append([py_launcher, "-3"])

    python_exe = shutil.which("python")
    if python_exe and Path(python_exe).resolve() != Path(sys.executable).resolve():
        candidates.append([python_exe])

    for cmd in candidates:
        result = subprocess.run(
            [*cmd, "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"使用系统 Python: {result.stdout.strip()}")
            return cmd

    print("未找到可用的系统 Python。请先安装 Python 3.8+，并勾选 Add Python to PATH。")
    pause(1)


def ensure_windows():
    if os.name != "nt":
        print("此初始化器仅支持 Windows。")
        pause(1)


def ensure_requirements():
    if not REQUIREMENTS.exists():
        print(f"未找到依赖文件: {REQUIREMENTS}")
        pause(1)


def create_venv():
    if venv_python().exists():
        print(f"已存在虚拟环境: {VENV_DIR}")
        return
    python_cmd = find_system_python()
    run([*python_cmd, "-m", "venv", str(VENV_DIR)])


def install_dependencies():
    py = venv_python()
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(py), "-m", "pip", "install", "-r", str(REQUIREMENTS)])


def verify_imports():
    py = venv_python()
    code = "\n".join([
        "import importlib, sys",
        f"mods = {list(REQUIRED_MODULES.keys())!r}",
        "failed = []",
        "for mod in mods:",
        "    try:",
        "        importlib.import_module(mod)",
        "        print(f'{mod}: OK')",
        "    except Exception as exc:",
        "        failed.append((mod, exc))",
        "        print(f'{mod}: FAIL: {type(exc).__name__}: {exc}')",
        "sys.exit(1 if failed else 0)",
    ])
    run([str(py), "-c", code])


def write_launcher():
    content = """@echo off
chcp 65001 >nul
cd /d "%~dp0"

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在请求管理员权限启动 QTE Auto Tool...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -WorkingDirectory '%~dp0' -Verb RunAs"
    exit /b
)

if exist ".venv\\Scripts\\python.exe" (
    ".venv\\Scripts\\python.exe" "main.py"
) else (
    python "main.py"
)

pause
"""
    RUN_BAT.write_text(content, encoding="utf-8")
    print(f"已生成启动脚本: {RUN_BAT}")


def main():
    ensure_windows()
    ensure_requirements()
    print("=== QTE Auto Tool 环境初始化 ===")
    print(f"项目目录: {PROJECT_DIR}")
    print(f"初始化器: {sys.executable}")
    create_venv()
    install_dependencies()
    verify_imports()
    write_launcher()
    print("\n初始化完成。")
    print("以后可以双击 run_qte.bat 启动程序。")
    pause(0)


if __name__ == "__main__":
    main()
