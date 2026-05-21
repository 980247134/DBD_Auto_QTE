# Cute_Cat v3.1

自动 QTE 技能检测工具。基于 AI 深度学习模型（MobileNet V3 Small + ONNX Runtime），实时识别屏幕中的技能检测画面，在指针进入完美判定区时自动触发按键。

---

## ⚠️ Model File Download

**重要**: 本项目不包含模型文件。请从以下地址下载模型文件：

👉 **https://github.com/Manuteaa/dbd_autoSkillCheck**

下载 `model.onnx` 后，放入 `models/` 文件夹中。

---

## 功能特点

### AI 模型检测

- 使用 MobileNet V3 Small 神经网络进行 11 类技能检测分类
- 支持所有 QTE 类型
- ONNX Runtime CPU 推理
- 模型测试精度 98.7%

### 11 类检测分类

### 截屏模式

- **屏幕中心**：自动截取屏幕中心 224×224 区域（MSS 直接截屏，低延迟）

### 双输入方式

- **PyDirectInput 软件输入**：通过 Windows API 发送 Space 键
- **Pico 2W USB 硬件输入**：通过 Raspberry Pi Pico 2W 作为 USB HID 键盘发送

### 控制方式

- WebUI 界面操作
- 全局热键 **F4** 暂停/继续

---

## 文件结构

```
Cute_Cat/
├── w7b.py              # WebUI 主程序 (Flask + Socket.IO)
├── x3m.py              # AI 推理和触发逻辑
├── v9d.py              # ONNX 模型推理封装
├── q2s.py              # Pico 2W USB 串口通信
├── templates/
│   └── index.html      # WebUI 前端页面
├── setup.bat           # 一键初始化（下载嵌入式 Python + 安装依赖）
├── run.bat             # 启动程序（自动请求管理员权限）
├── requirements.txt    # Python 依赖
├── app_config.json     # 配置文件
├── models/             # 模型目录（需下载 model.onnx 放入此处）
│   └── .gitkeep
└── pico2W/             # Pico 2W 固件
    ├── boot.py
    └── code.py
```

---

## 安装与启动

### 1. 下载 AI 模型

从 https://github.com/Manuteaa/dbd_autoSkillCheck 下载 `model.onnx`，放入 `models/` 文件夹中。

### 2. 初始化环境

双击 `setup.bat`，它会自动下载嵌入式 Python 并安装依赖。

### 3. 启动程序

双击 `run.bat`，它会启动 WebUI 服务并自动在浏览器中打开。

---

## 推荐参数

- **滞后**: 0ms

完整配置示例见 `app_config.json`。

---

## 🙏 Credits / 感谢

**AI 模型来源**：
- 📦 Model by **Manuteaa** from [dbd_autoSkillCheck](https://github.com/Manuteaa/dbd_autoSkillCheck)
- 📄 License: GPL-3.0

**其他感谢**：
- MobileNet V3 Small 架构来自 PyTorch torchvision

---

## 注意事项

- 本工具不会读取游戏内存
- 本工具不会注入游戏进程
- 最佳性能需要游戏和 AI 模型 FPS 都在 60 以上
- 在带反作弊或联网环境中使用自动化工具可能违反游戏服务条款，请自行承担风险

---

## 免责声明

本项目仅供学习、研究和单机游戏辅助使用。请勿用于破坏公平性的联网游戏或违反服务条款的场景。作者不对任何账号处罚、封禁、数据损失或其他后果负责。
