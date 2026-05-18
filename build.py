#!/usr/bin/env python3
"""
Build script for QTE Auto Tool
Handles PyInstaller packaging with proper resource inclusion.
"""

import glob
import os
import sys
import importlib.util
import shutil
import subprocess


def clean_build():
    """Remove previous build artifacts."""
    dirs = ['build', 'dist', '__pycache__']
    for d in dirs:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"Removed {d}/")
    for pattern in ['main.spec', '*.spec']:
        for f in glob.glob(pattern):
            os.remove(f)
            print(f"Removed {f}")
    print("Build environment cleaned.")


def build():
    """Run PyInstaller build."""
    print("\n=== QTE Auto Tool Build ===\n")

    # Ensure PyInstaller is installed
    if importlib.util.find_spec("PyInstaller") is None:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "QTE-Auto-Tool",
        "--onefile",           # Single executable
        "--windowed",          # No console window (GUI app)
        "--noconfirm",         # Overwrite without prompt
        "--clean",             # Clean PyInstaller cache
        "--add-data", "engine.py;.",
        "--add-data", "selector.py;.",
        "--add-data", "collapsible_frame.py;.",
        "--add-data", "usb_sender.py;.",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "numpy.core._multiarray_umath",
        "main.py"
    ]

    print("Running PyInstaller...")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0:
        print("\n✅ Build successful!")
        print("Output: dist/QTE-Auto-Tool.exe")

        # Copy additional files to dist
        if os.path.exists("qte_config.json"):
            shutil.copy("qte_config.json", "dist/")
            print("Copied: qte_config.json")
    else:
        print("\n❌ Build failed!")
        sys.exit(1)


if __name__ == "__main__":
    clean_build()
    build()
