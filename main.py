"""
QTE Auto Tool - Main GUI Application (v3.0)
AI model detection only (ONNX), no traditional CV.

Key Design:
- AI model detection only, ONNX runtime required
- No mode buttons, no Hyperfocus toggle: 480Hz auto-detects ALL speed changes
- Clean, minimal UI for in-game use
"""

import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np
import time
import json
import os
import sys
import threading
import ctypes
from ctypes import wintypes

from engine import QTEEngine
from usb_sender import get_pico_usb_sender
from ai_detector import AIDetector
from selector import RegionSelector
from collapsible_frame import CollapsibleFrame


class QTEGUI:

    BG = "#1a1a2e"
    BG_SECONDARY = "#16213e"
    FG = "#e0e0e0"
    ACCENT = "#e94560"
    SUCCESS = "#00d9ff"
    WARNING = "#ffd700"
    DANGER = "#ff4757"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("QTE Auto Tool v3.0 - AI Detection")
        self.root.geometry("1100x850")
        self.root.configure(bg=self.BG)
        self.root.minsize(950, 750)

        self.engine = QTEEngine()
        self.preview_after_id = None
        self.start_after_id = None
        self.config_file = "qte_config.json"
        self.status_overlay = None
        self.status_overlay_label = None
        self.hotkey_thread = None
        self.hotkey_stop_event = threading.Event()
        self.hotkey_thread_id = None

        self._build_ui()
        self._load_config()
        self._update_stats()
        self._start_global_hotkey()

    def _build_ui(self):
        title_frame = tk.Frame(self.root, bg=self.BG, height=50)
        title_frame.pack(fill=tk.X, padx=20, pady=(10, 0))
        title_frame.pack_propagate(False)

        tk.Label(title_frame, text="⚡ QTE AUTO TOOL",
                font=("JetBrains Mono", 22, "bold"),
                bg=self.BG, fg=self.ACCENT).pack(side=tk.LEFT)

        tk.Label(title_frame, text="AI Detection | F4 暂停/继续",
                font=("JetBrains Mono", 11),
                bg=self.BG, fg="#666").pack(side=tk.LEFT, padx=15, pady=8)

        content = tk.Frame(self.root, bg=self.BG)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        left = tk.Frame(content, bg=self.BG, width=380)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left.pack_propagate(False)

        self._build_region_section(left)
        self._build_capture_section(left)
        self._build_input_section(left)
        self._build_ai_config_section(left)
        self._build_control_section(left)
        self._build_param_section(left)
        self._build_feature_section(left)
        self._build_stats_section(left)
        self._build_log_section(left)

        right = tk.Frame(content, bg=self.BG)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._build_preview_section(right)
        self._build_status_section(right)

        status = tk.Frame(self.root, bg="#0f0f23", height=28)
        status.pack(fill=tk.X, side=tk.BOTTOM)
        status.pack_propagate(False)

        self.status_label = tk.Label(status, text="就绪 | 点击启动检测",
                                    bg="#0f0f23", fg=self.SUCCESS,
                                    font=("JetBrains Mono", 10), anchor="w")
        self.status_label.pack(side=tk.LEFT, padx=15, pady=3)

        self.fps_label = tk.Label(status, text="检测: -- Hz",
                                 bg="#0f0f23", fg="#888",
                                 font=("JetBrains Mono", 10))
        self.fps_label.pack(side=tk.RIGHT, padx=15, pady=3)

        self.speed_label_bar = tk.Label(status, text="速度: ---",
                                       bg="#0f0f23", fg=self.WARNING,
                                       font=("JetBrains Mono", 10))
        self.speed_label_bar.pack(side=tk.RIGHT, padx=15, pady=3)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _show_status_overlay(self, text: str, color: str):
        if self.status_overlay is None or not self.status_overlay.winfo_exists():
            self.status_overlay = tk.Toplevel(self.root)
            self.status_overlay.overrideredirect(True)
            self.status_overlay.attributes("-topmost", True)
            self.status_overlay.configure(bg="#111")
            self.status_overlay_label = tk.Label(
                self.status_overlay,
                text=text,
                bg="#111",
                fg=color,
                font=("JetBrains Mono", 12, "bold"),
                padx=12,
                pady=6,
            )
            self.status_overlay_label.pack()
        else:
            self.status_overlay_label.config(text=text, fg=color)

        self.status_overlay.update_idletasks()
        width = self.status_overlay.winfo_width()
        screen_w = self.status_overlay.winfo_screenwidth()
        x = screen_w - width - 20
        y = 20
        self.status_overlay.geometry(f"+{x}+{y}")
        self.status_overlay.deiconify()

    def _hide_status_overlay(self):
        if self.status_overlay is not None and self.status_overlay.winfo_exists():
            self.status_overlay.withdraw()

    def _set_overlay_state(self):
        if self.engine.running:
            if self.engine.paused:
                self._show_status_overlay("QTE 暂停", self.WARNING)
            else:
                self._show_status_overlay("QTE 运行", self.SUCCESS)
        else:
            self._hide_status_overlay()

    def _build_region_section(self, parent):
        card = CollapsibleFrame(parent, title="📍 监控区域", bg=self.BG, fg=self.FG)
        card.pack(fill=tk.X, pady=(0, 10))
        content = card.get_content_frame()

        self.region_label = tk.Label(content, text="未设置区域",
                                    bg=self.BG_SECONDARY, fg="#888",
                                    font=("JetBrains Mono", 10),
                                    width=35, height=2)
        self.region_label.pack(fill=tk.X, pady=5)

        btn_row = tk.Frame(content, bg=self.BG)
        btn_row.pack(fill=tk.X, pady=5)

        tk.Button(btn_row, text="🖱️ 全屏框选",
                 command=self._select_region,
                 bg=self.ACCENT, fg="white",
                 font=("JetBrains Mono", 10, "bold"),
                 width=12, cursor="hand2",
                 relief=tk.FLAT, padx=5, pady=3).pack(side=tk.LEFT, padx=2)

        tk.Button(btn_row, text="⌨️ 手动输入",
                 command=self._input_region,
                 bg=self.BG_SECONDARY, fg=self.FG,
                 font=("JetBrains Mono", 10),
                 width=12, cursor="hand2",
                 relief=tk.FLAT, padx=5, pady=3).pack(side=tk.LEFT, padx=2)

        tk.Button(btn_row, text="💾 保存",
                 command=self._save_config,
                 bg="#2d5a27", fg="white",
                 font=("JetBrains Mono", 10),
                 width=8, cursor="hand2",
                 relief=tk.FLAT, padx=5, pady=3).pack(side=tk.LEFT, padx=2)

    def _build_capture_section(self, parent):
        card = CollapsibleFrame(parent, title="🎥 图像采集方式", bg=self.BG, fg=self.SUCCESS)
        card.pack(fill=tk.X, pady=(0, 10))
        content = card.get_content_frame()

        self.capture_status_label = tk.Label(content, text="当前: MSS 直接截屏",
                                            bg=self.BG_SECONDARY, fg=self.SUCCESS,
                                            font=("JetBrains Mono", 10, "bold"),
                                            width=35, height=1)
        self.capture_status_label.pack(fill=tk.X, pady=(0, 8))

        backend_row = tk.Frame(content, bg=self.BG)
        backend_row.pack(fill=tk.X, pady=5)

        tk.Label(backend_row, text="选择方式:",
                bg=self.BG, fg="#aac",
                font=("JetBrains Mono", 9, "bold"),
                width=10, anchor="w").pack(side=tk.LEFT)

        self.capture_backend_var = tk.StringVar(value="mss")

        self.btn_mss = tk.Radiobutton(backend_row, text="MSS 截屏",
                      variable=self.capture_backend_var, value="mss",
                      command=self._update_capture_backend,
                      bg=self.BG, fg=self.FG,
                      selectcolor=self.BG_SECONDARY,
                      activebackground=self.BG,
                      activeforeground=self.SUCCESS,
                      font=("JetBrains Mono", 10, "bold"),
                      cursor="hand2")
        self.btn_mss.pack(side=tk.LEFT, padx=8)

        self.btn_obs = tk.Radiobutton(backend_row, text="OBS 虚拟摄像头",
                      variable=self.capture_backend_var, value="obs",
                      command=self._update_capture_backend,
                      bg=self.BG, fg=self.FG,
                      selectcolor=self.BG_SECONDARY,
                      activebackground=self.BG,
                      activeforeground=self.SUCCESS,
                      font=("JetBrains Mono", 10, "bold"),
                      cursor="hand2")
        self.btn_obs.pack(side=tk.LEFT, padx=8)

        self.obs_frame = tk.Frame(content, bg=self.BG)
        self.obs_frame.pack(fill=tk.X, pady=(8, 0))

        tk.Label(self.obs_frame, text="OBS编号:",
                bg=self.BG, fg="#aac",
                font=("JetBrains Mono", 9),
                width=10, anchor="w").pack(side=tk.LEFT)

        self.obs_index_var = tk.IntVar(value=0)
        tk.Scale(self.obs_frame, from_=0, to=10,
                orient=tk.HORIZONTAL,
                variable=self.obs_index_var,
                bg=self.BG, fg=self.FG,
                highlightthickness=0, length=100,
                showvalue=False,
                command=self._update_obs_index).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.obs_index_display = tk.Label(self.obs_frame, text="0",
                                          bg=self.BG_SECONDARY, fg=self.WARNING,
                                          font=("JetBrains Mono", 9, "bold"),
                                          width=6)
        self.obs_index_display.pack(side=tk.LEFT, padx=3)

        tk.Button(self.obs_frame, text="🔍 扫描",
                 command=self._scan_cameras,
                 bg=self.ACCENT, fg="white",
                 font=("JetBrains Mono", 8, "bold"),
                 width=6, cursor="hand2",
                 relief=tk.FLAT, padx=3, pady=2).pack(side=tk.LEFT)

        tip_text = "MSS: 直接截屏，低延迟\nOBS: 通过虚拟摄像头，兼容性好\n点击'扫描'查找可用摄像头"
        tk.Label(content, text=tip_text,
                bg=self.BG, fg="#888",
                font=("JetBrains Mono", 8),
                justify=tk.LEFT).pack(pady=(5, 0))

    def _build_input_section(self, parent):
        card = CollapsibleFrame(parent, title="⌨️ 输入方式", bg=self.BG, fg=self.SUCCESS)
        card.pack(fill=tk.X, pady=(0, 10))
        content = card.get_content_frame()

        self.input_status_label = tk.Label(content, text="当前: PyDirectInput 软件输入",
                                           bg=self.BG_SECONDARY, fg=self.SUCCESS,
                                           font=("JetBrains Mono", 10, "bold"),
                                           width=35, height=1)
        self.input_status_label.pack(fill=tk.X, pady=(0, 8))

        input_row = tk.Frame(content, bg=self.BG)
        input_row.pack(fill=tk.X, pady=5)

        tk.Label(input_row, text="选择方式:",
                bg=self.BG, fg="#aac",
                font=("JetBrains Mono", 9, "bold"),
                width=10, anchor="w").pack(side=tk.LEFT)

        self.input_method_var = tk.StringVar(value="pydirectinput")

        self.btn_pydirect = tk.Radiobutton(input_row, text="软件输入",
                      variable=self.input_method_var, value="pydirectinput",
                      command=self._update_input_method,
                      bg=self.BG, fg=self.FG,
                      selectcolor=self.BG_SECONDARY,
                      activebackground=self.BG,
                      activeforeground=self.SUCCESS,
                      font=("JetBrains Mono", 10, "bold"),
                      cursor="hand2")
        self.btn_pydirect.pack(side=tk.LEFT, padx=8)

        self.btn_pico = tk.Radiobutton(input_row, text="Pico 2W 硬件 (USB)",
                      variable=self.input_method_var, value="pico2w",
                      command=self._update_input_method,
                      bg=self.BG, fg=self.FG,
                      selectcolor=self.BG_SECONDARY,
                      activebackground=self.BG,
                      activeforeground=self.SUCCESS,
                      font=("JetBrains Mono", 10, "bold"),
                      cursor="hand2")
        self.btn_pico.pack(side=tk.LEFT, padx=8)

        self.pico_frame = tk.Frame(content, bg=self.BG)
        self.pico_frame.pack(fill=tk.X, pady=(8, 0))

        tk.Label(self.pico_frame, text="USB端口:",
                bg=self.BG, fg="#aac",
                font=("JetBrains Mono", 9),
                width=10, anchor="w").pack(side=tk.LEFT)

        self.pico_address_var = tk.StringVar(value="未连接")
        self.pico_address_label = tk.Label(self.pico_frame,
                                           textvariable=self.pico_address_var,
                                           bg=self.BG_SECONDARY, fg="#888",
                                           font=("JetBrains Mono", 8),
                                           width=20, anchor="w")
        self.pico_address_label.pack(side=tk.LEFT, padx=5)

        tk.Button(self.pico_frame, text="🔍 扫描",
                 command=self._scan_pico_devices,
                 bg=self.ACCENT, fg="white",
                 font=("JetBrains Mono", 8, "bold"),
                 width=6, cursor="hand2",
                 relief=tk.FLAT, padx=3, pady=2).pack(side=tk.LEFT, padx=2)

        self.btn_pico_connect = tk.Button(self.pico_frame, text="连接",
                 command=self._connect_pico,
                 bg="#2d5a27", fg="white",
                 font=("JetBrains Mono", 8, "bold"),
                 width=6, cursor="hand2",
                 relief=tk.FLAT, padx=3, pady=2)
        self.btn_pico_connect.pack(side=tk.LEFT, padx=2)

        tip_text = "软件输入: PyDirectInput\nPico 2W: USB 硬件输入，更低延迟"
        tip_color = "#888"

        tk.Label(content, text=tip_text,
                bg=self.BG, fg=tip_color,
                font=("JetBrains Mono", 8),
                justify=tk.LEFT).pack(pady=(5, 0))

    def _build_ai_config_section(self, parent):
        card = CollapsibleFrame(parent, title="🧠 AI 模型配置", bg=self.BG, fg=self.WARNING)
        card.pack(fill=tk.X, pady=(0, 10))
        content = card.get_content_frame()

        model_row = tk.Frame(content, bg=self.BG)
        model_row.pack(fill=tk.X, pady=3)

        tk.Label(model_row, text="模型文件:",
                bg=self.BG, fg="#aac",
                font=("JetBrains Mono", 9),
                width=10, anchor="w").pack(side=tk.LEFT)

        self.ai_model_var = tk.StringVar(value="未选择")
        self.ai_model_menu = tk.OptionMenu(model_row, self.ai_model_var, "未选择")
        self.ai_model_menu.config(bg=self.BG_SECONDARY, fg=self.FG,
                                  font=("JetBrains Mono", 9),
                                  highlightthickness=0, width=16,
                                  activebackground=self.BG,
                                  activeforeground=self.SUCCESS)
        self.ai_model_menu.pack(side=tk.LEFT, padx=5)

        tk.Button(model_row, text="🔍",
                 command=self._scan_models,
                 bg=self.ACCENT, fg="white",
                 font=("JetBrains Mono", 8, "bold"),
                 width=3, cursor="hand2",
                 relief=tk.FLAT, padx=3, pady=2).pack(side=tk.LEFT, padx=2)

        device_row = tk.Frame(content, bg=self.BG)
        device_row.pack(fill=tk.X, pady=3)

        tk.Label(device_row, text="推理设备:",
                bg=self.BG, fg="#aac",
                font=("JetBrains Mono", 9),
                width=10, anchor="w").pack(side=tk.LEFT)

        self.ai_device_var = tk.StringVar(value="cpu")
        tk.Radiobutton(device_row, text="CPU",
                      variable=self.ai_device_var, value="cpu",
                      bg=self.BG, fg=self.FG,
                      selectcolor=self.BG_SECONDARY,
                      font=("JetBrains Mono", 9),
                      cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(device_row, text="GPU",
                      variable=self.ai_device_var, value="gpu",
                      bg=self.BG, fg=self.FG,
                      selectcolor=self.BG_SECONDARY,
                      font=("JetBrains Mono", 9),
                      cursor="hand2").pack(side=tk.LEFT, padx=5)

        ante_row = tk.Frame(content, bg=self.BG)
        ante_row.pack(fill=tk.X, pady=3)

        tk.Label(ante_row, text="预判延迟:",
                bg=self.BG, fg="#aac",
                font=("JetBrains Mono", 9),
                width=10, anchor="w").pack(side=tk.LEFT)

        self.ai_ante_var = tk.IntVar(value=20)
        tk.Scale(ante_row, from_=0, to=50, resolution=5,
                orient=tk.HORIZONTAL, variable=self.ai_ante_var,
                bg=self.BG, fg=self.FG,
                highlightthickness=0, length=100,
                showvalue=False,
                command=self._update_ai_ante).pack(side=tk.LEFT, padx=5)

        self.ai_ante_display = tk.Label(ante_row, text="20ms",
                                        bg=self.BG_SECONDARY, fg=self.WARNING,
                                        font=("JetBrains Mono", 9, "bold"),
                                        width=6)
        self.ai_ante_display.pack(side=tk.LEFT)

        threads_row = tk.Frame(content, bg=self.BG)
        threads_row.pack(fill=tk.X, pady=3)

        tk.Label(threads_row, text="CPU线程:",
                bg=self.BG, fg="#aac",
                font=("JetBrains Mono", 9),
                width=10, anchor="w").pack(side=tk.LEFT)

        self.ai_threads_var = tk.IntVar(value=4)
        tk.Scale(threads_row, from_=1, to=8,
                orient=tk.HORIZONTAL, variable=self.ai_threads_var,
                bg=self.BG, fg=self.FG,
                highlightthickness=0, length=100,
                showvalue=False,
                command=self._update_ai_threads).pack(side=tk.LEFT, padx=5)

        self.ai_threads_display = tk.Label(threads_row, text="4",
                                           bg=self.BG_SECONDARY, fg=self.WARNING,
                                           font=("JetBrains Mono", 9, "bold"),
                                           width=6)
        self.ai_threads_display.pack(side=tk.LEFT)

        capture_row = tk.Frame(content, bg=self.BG)
        capture_row.pack(fill=tk.X, pady=3)

        tk.Label(capture_row, text="截取模式:",
                bg=self.BG, fg="#aac",
                font=("JetBrains Mono", 9),
                width=10, anchor="w").pack(side=tk.LEFT)

        self.ai_capture_var = tk.StringVar(value="region")
        tk.Radiobutton(capture_row, text="选定区域",
                      variable=self.ai_capture_var, value="region",
                      bg=self.BG, fg=self.FG,
                      selectcolor=self.BG_SECONDARY,
                      font=("JetBrains Mono", 9),
                      cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(capture_row, text="屏幕中心",
                      variable=self.ai_capture_var, value="center",
                      bg=self.BG, fg=self.FG,
                      selectcolor=self.BG_SECONDARY,
                      font=("JetBrains Mono", 9),
                      cursor="hand2").pack(side=tk.LEFT, padx=5)

        tip_text = "ONNX模型识别，支持所有QTE类型\n模型下载: github.com/Manuteaa/dbd_autoSkillCheck/releases\n放置到 models/ 目录即可"
        tk.Label(content, text=tip_text,
                bg=self.BG, fg="#888",
                font=("JetBrains Mono", 8),
                justify=tk.LEFT).pack(pady=(5, 0))

        self._scan_models()

    def _update_ai_ante(self, value):
        val = int(value)
        self.engine.ai_hit_ante_ms = val
        self.ai_ante_display.config(text=f"{val}ms")

    def _update_ai_threads(self, value):
        val = int(value)
        self.engine.ai_cpu_threads = val
        self.ai_threads_display.config(text=str(val))

    def _scan_models(self):
        models = AIDetector.scan_models()
        model_names = [m["name"] for m in models]
        self._available_models = models

        menu = self.ai_model_menu["menu"]
        menu.delete(0, tk.END)

        if model_names:
            for name in model_names:
                menu.add_command(label=name,
                                command=lambda n=name: self.ai_model_var.set(n))
            self.ai_model_var.set(model_names[0])
            self._log(f"找到 {len(models)} 个 AI 模型: {', '.join(model_names)}")
        else:
            menu.add_command(label="未找到模型",
                            command=lambda: self.ai_model_var.set("未找到模型"))
            self.ai_model_var.set("未找到模型")
            self._log("未找到 AI 模型，请将 .onnx 文件放入 models/ 目录")

    def _build_control_section(self, parent):
        card = tk.Frame(parent, bg=self.BG)
        card.pack(fill=tk.X, pady=10)

        self.btn_start = tk.Button(card, text="▶  启动检测",
                                  command=self._start,
                                  bg="#0f3460", fg="#00ff88",
                                  font=("JetBrains Mono", 12, "bold"),
                                  width=14, height=2,
                                  cursor="hand2", relief=tk.FLAT)
        self.btn_start.pack(side=tk.LEFT, padx=3)

        self.btn_pause = tk.Button(card, text="⏸  暂停",
                                  command=self._pause,
                                  bg=self.BG_SECONDARY, fg=self.FG,
                                  font=("JetBrains Mono", 12),
                                  width=10, height=2,
                                  state=tk.DISABLED,
                                  cursor="hand2", relief=tk.FLAT)
        self.btn_pause.pack(side=tk.LEFT, padx=3)

        self.btn_stop = tk.Button(card, text="⏹  停止",
                                 command=self._stop,
                                 bg=self.BG_SECONDARY, fg=self.DANGER,
                                 font=("JetBrains Mono", 12),
                                 width=10, height=2,
                                 state=tk.DISABLED,
                                 cursor="hand2", relief=tk.FLAT)
        self.btn_stop.pack(side=tk.LEFT, padx=3)

    def _build_param_section(self, parent):
        card = CollapsibleFrame(parent, title="⚙️ 检测参数", bg=self.BG, fg=self.FG)
        card.pack(fill=tk.X, pady=10)
        content = card.get_content_frame()

        params = [
            ("检测频率", "target_hz", "Hz", 120, 1000, 500,
             "屏幕检测循环频率，建议480Hz"),
            ("触发冷却", "cooldown_ms", "ms", 0, 200, 30,
             "每次触发后的锁定时间，防止连发"),
        ]

        self.param_vars = {}
        self.param_displays = {}

        for label, attr, unit, min_v, max_v, default, tooltip in params:
            row = tk.Frame(content, bg=self.BG)
            row.pack(fill=tk.X, pady=4)

            lbl = tk.Label(row, text=f"{label}:",
                          bg=self.BG, fg="#aaa",
                          font=("JetBrains Mono", 9),
                          width=12, anchor="w")
            lbl.pack(side=tk.LEFT)

            var = tk.IntVar(value=default)
            self.param_vars[attr] = var

            scale = tk.Scale(row, from_=min_v, to=max_v,
                           orient=tk.HORIZONTAL, variable=var,
                           bg=self.BG, fg=self.FG,
                           highlightthickness=0, length=140,
                           showvalue=False,
                           command=lambda v, a=attr: self._update_param(a, v))
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

            val_lbl = tk.Label(row, text=f"{default}{unit}",
                              bg=self.BG_SECONDARY, fg=self.SUCCESS,
                              font=("JetBrains Mono", 9, "bold"),
                              width=8)
            val_lbl.pack(side=tk.LEFT)
            self.param_displays[attr] = val_lbl

            for widget in [lbl, scale, val_lbl]:
                widget.bind("<Enter>", lambda e, t=tooltip: self._show_tooltip(t))
                widget.bind("<Leave>", lambda e: self._hide_tooltip())

    def _build_feature_section(self, parent):
        card = CollapsibleFrame(parent, title="🔬 高级设置", bg=self.BG, fg=self.FG)
        card.pack(fill=tk.X, pady=10)
        content = card.get_content_frame()

        save_frame = tk.Frame(content, bg=self.BG)
        save_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(save_frame, text="💾 保存当前配置",
                 command=self._save_config,
                 bg="#2d5a27", fg="white",
                 font=("JetBrains Mono", 10, "bold"),
                 cursor="hand2", relief=tk.FLAT,
                 padx=8, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(save_frame, text="保存频率/区域/AI配置",
                 bg=self.BG, fg="#888",
                 font=("JetBrains Mono", 8)).pack(side=tk.LEFT, padx=8)

    def _build_stats_section(self, parent):
        card = CollapsibleFrame(parent, title="📊 实时统计", bg=self.BG, fg=self.FG)
        card.pack(fill=tk.X, pady=10)
        content = card.get_content_frame()

        self.stats_labels = {}
        stats_config = [
            ("avg_latency", "平均延迟", "ms", self.SUCCESS),
            ("p99_latency", "P99延迟", "ms", self.WARNING),
            ("max_latency", "最大延迟", "ms", self.DANGER),
            ("trigger_count", "触发次数", "", self.SUCCESS),
            ("frame_count", "检测帧数", "", "#888"),
            ("hit_rate", "命中率", "%", self.SUCCESS),
            ("ai_prediction", "AI识别", "", self.WARNING),
            ("ai_provider", "推理设备", "", self.WARNING),
        ]

        for i, (key, name, unit, color) in enumerate(stats_config):
            row = tk.Frame(content, bg=self.BG)
            row.pack(fill=tk.X, pady=2)

            tk.Label(row, text=f"{name}:",
                    bg=self.BG, fg="#888",
                    font=("JetBrains Mono", 9),
                    width=12, anchor="w").pack(side=tk.LEFT)

            lbl = tk.Label(row, text="--",
                          bg=self.BG_SECONDARY, fg=color,
                          font=("JetBrains Mono", 10, "bold"),
                          width=18)
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            self.stats_labels[key] = lbl

    def _build_log_section(self, parent):
        card = CollapsibleFrame(parent, title="📝 事件日志", bg=self.BG, fg=self.FG)
        card.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        content = card.get_content_frame()

        self.log_text = tk.Text(content, bg="#0a0a1a", fg="#0f0",
                               font=("JetBrains Mono", 9),
                               wrap=tk.WORD, state=tk.DISABLED,
                               height=8, padx=5, pady=5)
        self.log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scrollbar = tk.Scrollbar(content, command=self.log_text.yview,
                                bg=self.BG_SECONDARY)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        self.log_text.config(yscrollcommand=scrollbar.set)

        tk.Button(content, text="🗑️", command=self._clear_log,
                 bg=self.BG_SECONDARY, fg="#888",
                 font=("JetBrains Mono", 8),
                 width=3, cursor="hand2",
                 relief=tk.FLAT).place(relx=0.98, rely=0.02, anchor="ne")

    def _build_preview_section(self, parent):
        card = tk.LabelFrame(parent, text="👁️ 实时预览",
                            bg=self.BG, fg=self.FG)
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.preview_label = tk.Label(card, bg="#000",
                                     text="等待启动...",
                                     fg="#444",
                                     font=("JetBrains Mono", 14))
        self.preview_label.pack(padx=5, pady=5)

        legend = tk.Frame(card, bg=self.BG)
        legend.pack(fill=tk.X, pady=(5, 0))

        for color_text, desc in [("🔴 红色", "指针"), ("🟢 绿色", "判定区"),
                                  ("🟡 黄圈", "命中")]:
            tk.Label(legend, text=f"{color_text}={desc}",
                    bg=self.BG, fg="#888",
                    font=("JetBrains Mono", 8)).pack(side=tk.LEFT, padx=6)

    def _build_status_section(self, parent):
        card = CollapsibleFrame(parent, title="🎯 自动检测状态", bg=self.BG, fg=self.FG)
        card.pack(fill=tk.X, pady=(0, 10))
        content = card.get_content_frame()

        row1 = tk.Frame(content, bg=self.BG)
        row1.pack(fill=tk.X, pady=3)

        tk.Label(row1, text="自动识别:",
                bg=self.BG, fg="#888",
                font=("JetBrains Mono", 9),
                width=12, anchor="w").pack(side=tk.LEFT)

        self.mode_indicator = tk.Label(row1, text="---",
                                       bg=self.BG_SECONDARY, fg=self.SUCCESS,
                                       font=("JetBrains Mono", 10, "bold"))
        self.mode_indicator.pack(side=tk.LEFT, padx=5)

        self.speed_indicator = tk.Label(row1, text="0°/s",
                                        bg=self.BG_SECONDARY, fg=self.SUCCESS,
                                        font=("JetBrains Mono", 10, "bold"))
        self.speed_indicator.pack(side=tk.LEFT, padx=15)

    # === Event Handlers ===

    def _select_region(self):
        self._log("启动区域选择器...")
        self.root.iconify()
        self.root.after(600, self._do_select)

    def _do_select(self):
        selector = RegionSelector()
        region = selector.run()
        self.root.deiconify()

        if region and region["width"] > 20 and region["height"] > 20:
            self.engine.set_region(**region)
            text = (f"X:{region['left']} Y:{region['top']} | "
                   f"{region['width']}×{region['height']}")
            self.region_label.config(text=text, fg=self.SUCCESS)
            self._log(f"区域已设置: {text}")
        else:
            self._log("区域选择取消或区域过小")

    def _input_region(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("输入坐标")
        dialog.geometry("320x240")
        dialog.configure(bg=self.BG)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        tk.Label(dialog, text="手动输入监控区域",
                bg=self.BG, fg=self.ACCENT,
                font=("JetBrains Mono", 12, "bold")).pack(pady=10)

        fields = {}
        for label, key, hint in [("Left X", "left", "X坐标"),
                                  ("Top Y", "top", "Y坐标"),
                                  ("Width", "width", "宽度(建议200)"),
                                  ("Height", "height", "高度(建议200)")]:
            row = tk.Frame(dialog, bg=self.BG)
            row.pack(fill=tk.X, padx=15, pady=4)
            tk.Label(row, text=f"{label}:",
                    bg=self.BG, fg="#aaa",
                    font=("JetBrains Mono", 10),
                    width=10, anchor="w").pack(side=tk.LEFT)
            entry = tk.Entry(row, bg=self.BG_SECONDARY, fg="white",
                           font=("JetBrains Mono", 10),
                           width=12, justify="center")
            entry.pack(side=tk.LEFT, padx=5)
            fields[key] = entry

        def confirm():
            try:
                region = {k: int(v.get()) for k, v in fields.items()}
                if all(v > 0 for v in region.values()):
                    self.engine.set_region(**region)
                    text = (f"X:{region['left']} Y:{region['top']} | "
                           f"{region['width']}×{region['height']}")
                    self.region_label.config(text=text, fg=self.SUCCESS)
                    self._log(f"手动输入区域: {text}")
                    dialog.destroy()
                else:
                    messagebox.showwarning("警告", "所有值必须大于0")
            except ValueError:
                messagebox.showerror("错误", "请输入有效整数")

        tk.Button(dialog, text="确认", command=confirm,
                 bg=self.ACCENT, fg="white",
                 font=("JetBrains Mono", 11, "bold"),
                 width=15, cursor="hand2",
                 relief=tk.FLAT, pady=5).pack(pady=15)

    def _update_capture_backend(self):
        backend = self.capture_backend_var.get()
        self.engine.capture_backend = backend

        if backend == "mss":
            self.capture_status_label.config(
                text="当前: MSS 直接截屏",
                fg=self.SUCCESS
            )
            self._log("切换到 MSS 直接截屏模式")
        else:
            self.capture_status_label.config(
                text=f"当前: OBS 虚拟摄像头 (编号 {self.obs_index_var.get()})",
                fg=self.WARNING
            )
            self._log(f"切换到 OBS 虚拟摄像头模式 (编号 {self.obs_index_var.get()})")

    def _update_obs_index(self, value):
        val = int(value)
        self.engine.obs_camera_index = val
        self.obs_index_display.config(text=str(val))
        if self.engine._obs_capture is not None:
            self.engine._obs_capture.release()
            self.engine._obs_capture = None

        if self.capture_backend_var.get() == "obs":
            self.capture_status_label.config(
                text=f"当前: OBS 虚拟摄像头 (编号 {val})",
                fg=self.WARNING
            )
            self._log(f"OBS 摄像头编号已更改为 {val}")

    def _update_input_method(self):
        method = self.input_method_var.get()
        self.engine.input_method = method

        if method == "pydirectinput":
            self.input_status_label.config(
                text="当前: PyDirectInput 软件输入",
                fg=self.SUCCESS
            )
            self._log("切换到 PyDirectInput 软件输入模式")
        else:
            pico_sender = get_pico_usb_sender()
            if pico_sender.connected:
                self.input_status_label.config(
                    text="当前: Pico 2W 硬件输入 (已连接)",
                    fg=self.SUCCESS
                )
                self._log("切换到 Pico 2W 硬件输入模式")
            else:
                self.input_status_label.config(
                    text="当前: Pico 2W 硬件输入 (未连接)",
                    fg=self.DANGER
                )
                self._log("⚠️ Pico 2W 未连接，请先扫描并连接设备")

    def _scan_pico_devices(self):
        self._log("=" * 45)
        self._log("开始扫描 Pico 2W USB 设备...")
        self.btn_pico_connect.config(state=tk.DISABLED)

        def scan_thread():
            try:
                pico_sender = get_pico_usb_sender()
                devices = pico_sender.scan_devices()

                self.root.after(0, lambda: self._on_pico_scan_complete(devices))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"扫描失败: {e}"))
                self.root.after(0, lambda: self.btn_pico_connect.config(state=tk.NORMAL))

        threading.Thread(target=scan_thread, daemon=True).start()

    def _on_pico_scan_complete(self, devices):
        self.btn_pico_connect.config(state=tk.NORMAL)

        if not devices:
            self._log("未找到 Pico 2W 设备")
            self._log("请确保:")
            self._log("  1. Pico 2W 已上传固件并启动")
            self._log("  2. Pico 2W 已通过 USB 连接到 PC")
            messagebox.showwarning("未找到设备",
                "未找到 Pico 2W 设备\n\n请确保:\n1. Pico 2W 已上传固件并启动\n2. USB 已连接")
            return

        self._log(f"找到 {len(devices)} 个设备:")
        for i, dev in enumerate(devices):
            self._log(f"  [{i}] {dev['port']} - {dev['description']}")

        if len(devices) == 1:
            self.pico_selected_port = devices[0]['port']
            self.pico_address_var.set(devices[0]['port'])
            self._log(f"自动选择: {devices[0]['description']}")
        else:
            device_list = [f"{d['description']} ({d['port']})" for d in devices]
            self.pico_selected_port = devices[0]['port']
            self.pico_address_var.set(devices[0]['port'])
            self._log(f"已选择第一个设备: {devices[0]['description']}")

    def _connect_pico(self):
        if not hasattr(self, 'pico_selected_port') or not self.pico_selected_port:
            messagebox.showwarning("提示", "请先扫描并选择设备")
            return

        self._log(f"正在连接到 {self.pico_selected_port}...")
        self.btn_pico_connect.config(state=tk.DISABLED, text="连接中...")

        def connect_thread():
            try:
                pico_sender = get_pico_usb_sender()
                success = pico_sender.connect(self.pico_selected_port)

                self.root.after(0, lambda: self._on_pico_connect_complete(success))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"连接失败: {e}"))
                self.root.after(0, lambda: self.btn_pico_connect.config(
                    state=tk.NORMAL, text="连接"))

        threading.Thread(target=connect_thread, daemon=True).start()

    def _on_pico_connect_complete(self, success):
        if success:
            pico_sender = get_pico_usb_sender()
            self.engine.pico_connection = pico_sender
            self.btn_pico_connect.config(text="断开", bg=self.DANGER)
            self.btn_pico_connect.config(state=tk.NORMAL, command=self._disconnect_pico)
            self.input_status_label.config(
                text="当前: Pico 2W 硬件输入 (已连接)",
                fg=self.SUCCESS
            )
            self._log("✓ Pico 2W 连接成功")
            messagebox.showinfo("成功", "Pico 2W 连接成功！\n\n现在可以使用硬件输入模式")
        else:
            self.btn_pico_connect.config(state=tk.NORMAL, text="连接")
            self._log("✗ Pico 2W 连接失败")
            messagebox.showerror("连接失败", "无法连接到 Pico 2W\n\n请检查设备状态")

    def _disconnect_pico(self):
        pico_sender = get_pico_usb_sender()
        pico_sender.disconnect()
        self.engine.pico_connection = None
        self.btn_pico_connect.config(text="连接", bg="#2d5a27", command=self._connect_pico)
        self.input_status_label.config(
            text="当前: Pico 2W 硬件输入 (未连接)",
            fg=self.DANGER
        )
        self._log("Pico 2W 已断开连接")

    def _scan_cameras(self):
        self._log("=" * 45)
        self._log("开始扫描摄像头...")

        cameras = []
        for i in range(10):
            backend = cv2.CAP_DSHOW if sys.platform == "win32" else 0
            cap = cv2.VideoCapture(i, backend)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cameras.append({"index": i, "resolution": f"{w}x{h}"})
                cap.release()
            else:
                cap.release()
                if i > 0 and len(cameras) == 0:
                    continue

        if not cameras:
            self._log("未找到任何可用摄像头")
            self._log("请确保:")
            self._log("  1. OBS 已启动")
            self._log("  2. 在 OBS 中点击了'启动虚拟摄像头'")
            messagebox.showwarning("未找到摄像头",
                                 "未找到任何可用摄像头\n\n请确保:\n1. OBS 已启动\n2. 在 OBS 中点击了'启动虚拟摄像头'")
        else:
            self._log(f"找到 {len(cameras)} 个可用摄像头:")
            for cam in cameras:
                self._log(f"  编号 {cam['index']}: {cam['resolution']}")

            if len(cameras) == 1:
                self.obs_index_var.set(cameras[0]['index'])
                self._update_obs_index(str(cameras[0]['index']))
                self._log(f"已自动选择摄像头 {cameras[0]['index']}")

            msg = f"找到 {len(cameras)} 个可用摄像头:\n\n"
            for cam in cameras:
                msg += f"编号 {cam['index']}: {cam['resolution']}\n"
            msg += "\n请在上方选择对应的编号"
            messagebox.showinfo("摄像头扫描结果", msg)

        self._log("=" * 45)

    def _update_param(self, attr: str, value: str):
        val = int(value)
        setattr(self.engine, attr, val)
        units = {"target_hz": "Hz", "cooldown_ms": "ms"}
        unit = units.get(attr, "")
        if attr in self.param_displays:
            self.param_displays[attr].config(text=f"{val}{unit}")

    def _start(self):
        if self.engine.region is None and self.ai_capture_var.get() != "center":
            messagebox.showwarning("警告", "请先设置监控区域")
            return

        selected_model = self.ai_model_var.get()
        if selected_model in ("未选择", "未找到模型"):
            messagebox.showwarning("警告", "请先选择 AI 模型文件\n\n将 .onnx 文件放入 models/ 目录后点击🔍扫描")
            return
        model_path = f"models/{selected_model}"
        if not os.path.exists(model_path):
            messagebox.showerror("错误", f"模型文件不存在: {model_path}")
            return

        self.engine.ai_model_path = model_path
        self.engine.ai_use_gpu = (self.ai_device_var.get() == "gpu")
        self.engine.ai_cpu_threads = self.ai_threads_var.get()
        self.engine.ai_hit_ante_ms = self.ai_ante_var.get()
        self.engine.ai_capture_mode = self.ai_capture_var.get()

        for attr, var in self.param_vars.items():
            setattr(self.engine, attr, var.get())

        self.engine.capture_backend = self.capture_backend_var.get()
        self.engine.obs_camera_index = self.obs_index_var.get()

        self.btn_start.config(state=tk.DISABLED, text="2秒后启动",
                             fg=self.WARNING)
        self.btn_pause.config(state=tk.DISABLED, text="⏸  暂停", fg=self.FG)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_label.config(text="请切回游戏窗口，2秒后开始检测", fg=self.WARNING)
        self._log("请在2秒内切回游戏窗口")
        self.start_after_id = self.root.after(2000, self._start_engine_after_focus_delay)

    def _start_engine_after_focus_delay(self):
        if self.engine.running:
            return
        if self.engine.region is None and self.engine.ai_capture_mode != "center":
            return

        self.start_after_id = None
        self.root.iconify()
        self.engine.start(preview=True)

        self.btn_start.config(state=tk.DISABLED, text="● 运行中",
                             fg=self.SUCCESS)
        self.btn_pause.config(state=tk.NORMAL, text="⏸  暂停", fg=self.FG)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_label.config(text="运行中 | F4暂停 点击停止结束", fg=self.SUCCESS)

        self._log("=" * 45)
        self._log(f"引擎启动 (AI 模型)")
        self._log(f"AI模型: {self.engine.ai_model_path}")
        self._log(f"推理设备: {'GPU' if self.engine.ai_use_gpu else 'CPU'}")
        self._log(f"截取模式: {self.engine.ai_capture_mode}")
        self._log(f"区域: {self.engine.region}")
        self._log(f"检测频率: {self.engine.target_hz}Hz")
        self._log("若触发次数增加但游戏无反应，请用管理员身份运行本程序")
        self._log("=" * 45)
        self._set_overlay_state()

        self._update_preview()

    def _pause(self):
        if not self.engine.running:
            return
        paused = self.engine.toggle_pause()
        if paused:
            self.btn_pause.config(text="▶  继续", fg=self.SUCCESS)
            self.status_label.config(text="已暂停", fg=self.WARNING)
            self._set_overlay_state()
            self._log("引擎暂停")
        else:
            self.btn_pause.config(text="⏸  暂停", fg=self.FG)
            self.status_label.config(text="运行中", fg=self.SUCCESS)
            self._set_overlay_state()
            self._log("引擎继续")

    def _stop(self):
        if self.start_after_id:
            self.root.after_cancel(self.start_after_id)
            self.start_after_id = None
        self.engine.stop()
        self.btn_start.config(state=tk.NORMAL, text="▶  启动检测", fg="#00ff88")
        self.btn_pause.config(state=tk.DISABLED, text="⏸  暂停", fg=self.FG)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_label.config(text="已停止 | 点击启动检测", fg=self.DANGER)
        self._set_overlay_state()
        self._log("引擎停止")

        if self.preview_after_id:
            self.root.after_cancel(self.preview_after_id)
            self.preview_after_id = None

        self.preview_label.config(image="", text="等待启动...", fg="#444")

    def _update_preview(self):
        if not self.engine.running:
            return

        preview = self.engine.latest_preview
        if preview is not None:
            try:
                img = Image.fromarray(preview)
                imgtk = ImageTk.PhotoImage(image=img)
                self.preview_label.imgtk = imgtk
                self.preview_label.config(image=imgtk, text="")
            except Exception:
                pass

        latencies = self.engine.latency_log
        if latencies:
            avg_lat = np.mean(latencies)
            if avg_lat > 0:
                actual_hz = 1000.0 / avg_lat
                self.fps_label.config(text=f"检测: {actual_hz:.0f} Hz")

        stats = self.engine.get_stats()
        ai_pred = stats.get("ai_prediction", "---")
        self.mode_indicator.config(text=ai_pred)
        self.speed_indicator.config(text="---")
        self.speed_label_bar.config(text=f"AI: {ai_pred}")

        self.preview_after_id = self.root.after(33, self._update_preview)

    def _update_stats(self):
        stats = self.engine.get_stats()
        for key, value in stats.items():
            if key in self.stats_labels:
                self.stats_labels[key].config(text=str(value))
        self.root.after(500, self._update_stats)

    def _log(self, msg: str):
        self.log_text.config(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _show_tooltip(self, text: str):
        self.status_label.config(text=text, fg="#888")

    def _hide_tooltip(self):
        status = "就绪 | 点击启动检测" if not self.engine.running else ("运行中" if not self.engine.paused else "已暂停")
        color = self.SUCCESS if self.engine.running and not self.engine.paused else (self.WARNING if self.engine.paused else self.SUCCESS)
        self.status_label.config(text=status, fg=color)

    def _save_config(self):
        config = {
            "version": "3.0",
            "region": self.engine.region,
            "params": {attr: var.get() for attr, var in self.param_vars.items()},
            "capture": {
                "backend": self.capture_backend_var.get(),
                "obs_camera_index": self.obs_index_var.get(),
            },
            "input": {
                "method": self.input_method_var.get(),
                "pico_usb_port": getattr(self, 'pico_selected_port', None),
            },
            "ai": {
                "model": self.ai_model_var.get(),
                "device": self.ai_device_var.get(),
                "ante_ms": self.ai_ante_var.get(),
                "threads": self.ai_threads_var.get(),
                "capture_mode": self.ai_capture_var.get(),
            },
        }
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            self._log(f"配置已保存: {self.config_file}")
            messagebox.showinfo("成功", "配置已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def _load_config(self):
        if not os.path.exists(self.config_file):
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            version = config.get("version", "1.0")
            if version != "3.0":
                self._log(f"配置版本 {version} 与当前版本 3.0 不完全兼容，尝试渐进加载")

            if config.get("region"):
                r = config["region"]
                self.engine.set_region(**r)
                text = (f"X:{r['left']} Y:{r['top']} | "
                       f"{r['width']}×{r['height']}")
                self.region_label.config(text=text, fg=self.SUCCESS)
                self._log(f"已加载保存的区域: {text}")

            for attr, val in config.get("params", {}).items():
                if attr in self.param_vars:
                    self.param_vars[attr].set(val)
                    self._update_param(attr, str(val))

            capture = config.get("capture", {})
            backend = capture.get("backend", "mss")
            if backend not in ("mss", "obs"):
                backend = "mss"
            obs_camera_index = int(capture.get("obs_camera_index", 0))
            self.capture_backend_var.set(backend)
            self.obs_index_var.set(obs_camera_index)
            self.engine.capture_backend = backend
            self.engine.obs_camera_index = obs_camera_index
            self.obs_index_display.config(text=str(obs_camera_index))

            if backend == "mss":
                self.capture_status_label.config(text="当前: MSS 直接截屏", fg=self.SUCCESS)
            else:
                self.capture_status_label.config(
                    text=f"当前: OBS 虚拟摄像头 (编号 {obs_camera_index})",
                    fg=self.WARNING
                )

            input_config = config.get("input", {})
            input_method = input_config.get("method", "pydirectinput")
            pico_port = input_config.get("pico_usb_port")

            if input_method in ("pydirectinput", "pico2w"):
                self.input_method_var.set(input_method)
                self.engine.input_method = input_method
                self._update_input_method()

                if pico_port and input_method == "pico2w":
                    self.pico_selected_port = pico_port
                    self.pico_address_var.set(pico_port)
                    self._log(f"已加载 Pico 端口: {pico_port}")

            ai_config = config.get("ai", config.get("detection", {}))
            self.ai_model_var.set(ai_config.get("model", ai_config.get("ai_model", "未选择")))
            self.ai_device_var.set(ai_config.get("device", ai_config.get("ai_device", "cpu")))
            self.ai_ante_var.set(ai_config.get("ante_ms", ai_config.get("ai_ante_ms", 20)))
            self.ai_threads_var.set(ai_config.get("threads", ai_config.get("ai_threads", 4)))
            self.ai_capture_var.set(ai_config.get("capture_mode", ai_config.get("ai_capture_mode", "region")))
            self._update_ai_ante(self.ai_ante_var.get())
            self._update_ai_threads(self.ai_threads_var.get())

            self._log(f"配置已加载 (版本 {version})")
        except Exception as e:
            self._log(f"配置加载失败: {e}")

    def _start_global_hotkey(self):
        if sys.platform != "win32":
            return
        self.hotkey_thread = threading.Thread(target=self._global_hotkey_loop, daemon=True)
        self.hotkey_thread.start()

    def _global_hotkey_loop(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.hotkey_thread_id = kernel32.GetCurrentThreadId()
        hotkey_id = 0x5154
        vk_f4 = 0x73

        if not user32.RegisterHotKey(None, hotkey_id, 0, vk_f4):
            self.root.after(0, lambda: self._log("全局热键 F4 注册失败（可能被其他程序占用）"))
            return

        self.root.after(0, lambda: self._log("全局热键 F4：暂停/继续 [已注册]"))

        try:
            msg = wintypes.MSG()
            while not self.hotkey_stop_event.is_set():
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0 or result == -1:
                    break
                if msg.message == 0x0312 and msg.wParam == hotkey_id:
                    self.root.after(0, self._on_f4_pressed)
        finally:
            user32.UnregisterHotKey(None, hotkey_id)

    def _stop_global_hotkey(self):
        if sys.platform != "win32":
            return
        self.hotkey_stop_event.set()
        if self.hotkey_thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.hotkey_thread_id, 0x0012, 0, 0)
        if self.hotkey_thread and self.hotkey_thread.is_alive():
            self.hotkey_thread.join(timeout=0.5)

    def _on_f4_pressed(self):
        try:
            self._log("[调试] F4 热键检测到")
            if self.engine.running:
                self._pause()
            else:
                self._log("[调试] 引擎未运行，忽略 F4")
        except Exception as e:
            self._log(f"[调试] F4处理异常: {e}")

    def _on_close(self):
        if self.start_after_id:
            self.root.after_cancel(self.start_after_id)
        self.engine.stop()
        if self.preview_after_id:
            self.root.after_cancel(self.preview_after_id)
        self._stop_global_hotkey()
        if self.status_overlay is not None and self.status_overlay.winfo_exists():
            self.status_overlay.destroy()
        self.root.destroy()


def main():
    root = tk.Tk()
    QTEGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
