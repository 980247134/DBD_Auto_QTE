# Release Notes - Cute_Cat v3.1

## 📦 Release Package: `Cute_Cat_v3.1.zip`

### What's New ✨

- ✅ WebUI based on Flask + Socket.IO (replacing old tkinter GUI)
- ✅ Removed all GPU inference code, simplified to CPU-only
- ✅ Removed OBS support, only MSS screen capture
- ✅ Removed tkinter dependencies (cleaner and lighter)
- ✅ All filenames and code are obfuscated for privacy
- ✅ Removed capture_mode config (now fixed to center mode only)
- ✅ Updated setup.bat with fewer steps
- ✅ Cleaned up dead code

---

## ⚠️ Important: Model File Download

**This package does NOT include the AI model file!**

You need to download `model.onnx` separately from:
👉 **https://github.com/Manuteaa/dbd_autoSkillCheck**

After downloading, place `model.onnx` into the `models/` folder.

---

## 🚀 Quick Start

### Prerequisites

- Windows operating system
- Administrator privileges (for key simulation)

### Installation Steps

1. Download `Cute_Cat_v3.1.zip` from GitHub Releases
2. Extract the zip file to a folder of your choice
3. **Download model.onnx** from https://github.com/Manuteaa/dbd_autoSkillCheck and place in `models/` folder
4. Run `setup.bat` to initialize the environment (downloads embedded Python)
5. After setup completes, run `run.bat` to start the program
6. WebUI will open automatically in your browser

---

## 📁 Package Structure

```
Cute_Cat/
├── w7b.py              # WebUI backend
├── x3m.py              # Core engine
├── v9d.py              # ONNX model wrapper
├── q2s.py              # Pico2W USB communication
├── setup.bat           # Environment setup script
├── run.bat             # Launch script
├── requirements.txt    # Python dependencies
├── app_config.json     # Configuration file
├── README.md           # Project documentation
├── templates/
│   └── index.html      # WebUI frontend
├── pico2W/             # Pico2W firmware
│   ├── boot.py
│   └── code.py
└── models/             # Model directory (place model.onnx here)
    └── .gitkeep
```

---

## 🙏 Credits

**AI Model Source**:
- 📦 Model by **Manuteaa** from [dbd_autoSkillCheck](https://github.com/Manuteaa/dbd_autoSkillCheck)
- 📄 License: GPL-3.0

---

## ⚠️ Important Notes

1. **Model File**: You must download `model.onnx` separately (not included in this release due to size)
2. **Admin Rights**: Required for PyDirectInput to simulate key presses
3. **Windows Only**: This project is Windows-only due to screen capture and input methods
4. **Anti-Cheat**: Usage in online games may violate anti-cheat policies

---

## 🐛 Reporting Issues

Please report issues on GitHub Issues page.
