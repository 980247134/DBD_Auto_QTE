#!/usr/bin/env python3
import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent


def run(cmd):
    print(f"> {' '.join(str(c) for c in cmd)}")
    subprocess.check_call(cmd, cwd=str(PROJECT_DIR))


def main():
    if importlib.util.find_spec("PyInstaller") is None:
        run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    run([
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "initialize",
        "--onefile",
        "--console",
        "--noconfirm",
        "--clean",
        "initialize.py",
    ])

    output = PROJECT_DIR / "dist" / "initialize.exe"
    if output.exists():
        target = PROJECT_DIR / "initialize.exe"
        target.write_bytes(output.read_bytes())
        print(f"\n已生成: {target}")
    else:
        raise FileNotFoundError(output)


if __name__ == "__main__":
    main()
