# QTE Auto Tool v3.0

黎明杀机（DBD）QTE 自动技能检测工具。基于 AI 深度学习模型（MobileNet V3 Small + ONNX Runtime），实时识别屏幕中的技能检测画面，在指针进入完美判定区时自动触发按键。

---

## 功能特点

### AI 模型检测

- 使用 MobileNet V3 Small 神经网络进行 11 类技能检测分类
- 支持所有 QTE 类型：修复/治疗、全白、全黑、挣扎、特殊技能（Decisive Strike / Oppression / Brand New Part 等）
- ONNX Runtime 推理，支持 CPU 和 GPU（CUDA / DirectML）
- 模型测试精度 98.7%

### 11 类检测分类

| 类别 | 描述 | 是否触发 |
|------|------|----------|
| 0 | 无 QTE | 否 |
| 1 | 修复/治疗 (完美) | ✅ |
| 2 | 修复/治疗 (接近) | ✅ |
| 3 | 修复/治疗 (外部) | 否 |
| 4 | 全白 (完美) | ✅ |
| 5 | 全白 (外部) | 否 |
| 6 | 全黑 (完美) | ✅ |
| 7 | 全黑 (外部) | 否 |
| 8 | 挣扎 (完美) | ✅ |
| 9 | 挣扎 (边界) | 否 |
| 10 | 挣扎 (外部) | 否 |

### Ante-Frontier 预判机制

当模型检测到指针接近完美判定区（类别 2）时，可配置预判延迟（0-50ms），提前触发按键以补偿游戏输入延迟。

### 双截屏模式

- **选定区域**：框选 QTE 区域，自动缩放到 224×224 输入模型
- **屏幕中心**：自动截取屏幕中心 224×224 区域，与模型训练数据一致

### 双输入方式

- **PyDirectInput 软件输入**：通过 Windows API 发送 Space 键
- **Pico 2W USB 硬件输入**：通过 Raspberry Pi Pico 2W 作为 USB HID 键盘发送，延迟 < 1ms，从原理上绕过软件层面按键注入检测

### 控制方式

- 点击 **启动检测** 开始
- 点击 **暂停 / 继续** 控制运行
- 全局热键 **F4** 暂停/继续
- 启动后有 2 秒倒计时，方便切回游戏窗口
- 运行时右上角显示状态：`QTE 运行` 或 `QTE 暂停`

### 配置保存

GUI 中提供 **保存当前配置** 按钮，可保存：

- 监控区域
- 检测频率 / 触发冷却
- 截屏方式（MSS / OBS）
- 输入方式（软件 / Pico 2W）
- AI 模型配置（模型文件 / 推理设备 / 预判延迟 / CPU 线程 / 截取模式）

---

## 文件结构

```text
DBD_Auto_QTE/
├── main.py                  # GUI 主程序
├── engine.py                # AI 推理和触发逻辑
├── ai_detector.py           # ONNX 模型推理封装
├── selector.py              # 全屏区域选择器
├── collapsible_frame.py     # 可折叠 UI 组件
├── usb_sender.py            # Pico 2W USB 串口通信
├── initialize.py            # 初始化脚本
├── initialize.exe           # 一键初始化工具
├── run_qte.bat              # 管理员权限启动脚本
├── build.py                 # 主程序打包脚本
├── build_initialize.py      # 初始化器打包脚本
├── requirements.txt         # Python 依赖
├── qte_config.json          # 配置文件
├── models/                  # AI 模型目录
│   └── model.onnx           # ONNX 模型文件（需下载）
├── docs/                    # 使用文档
│   ├── OBS配置指南.md
│   ├── OBS命令行使用指南.md
│   ├── OBS裁剪模式配置指南.md
│   ├── PICO_SETUP.md
│   └── PICO_USB_SETUP.md
└── pico_firmware/           # Pico 2W 固件
    ├── boot.py              # USB 配置
    └── code.py              # 固件主程序
```

---

## 安装与启动

### 1. 下载 AI 模型

从 [Manuteaa/dbd_autoSkillCheck Releases](https://github.com/Manuteaa/dbd_autoSkillCheck/releases) 下载 `model.onnx`，放入 `models/` 目录。

### 2. 安装依赖

#### 推荐方式：initialize.exe

双击：

```text
initialize.exe
```

它会自动：

1. 创建 `.venv` 虚拟环境。
2. 安装依赖（含 onnxruntime）。
3. 验证关键模块。
4. 生成 `run_qte.bat`。

初始化完成后，双击：

```text
run_qte.bat
```

#### 手动方式

```bash
pip install -r requirements.txt
python main.py
```

#### GPU 推理（可选）

如需 GPU 加速推理：

```bash
pip uninstall onnxruntime
pip install onnxruntime-gpu
```

然后安装 [CUDA](https://developer.nvidia.com/cuda-downloads) 和 [cuDNN](https://developer.nvidia.com/cudnn)，在 GUI 中选择 GPU 推理设备。

---

## 使用步骤

### 1. 设置监控区域

点击 **全屏框选**，框住 QTE 圆环区域。

建议：

- 区域完整包含 QTE 圆环。
- 尽量减少无关背景。
- 1080p 下推荐区域约 `160×160`。

或者选择 **屏幕中心** 截取模式，自动截取屏幕中心 224×224 区域（需 1920×1080 分辨率）。

### 2. 配置 AI 模型

在 **🧠 AI 模型配置** 面板中：

1. 点击 **🔍** 扫描 `models/` 目录中的模型文件
2. 选择模型文件
3. 选择推理设备（CPU / GPU）
4. 调整预判延迟（建议 20ms）
5. 选择截取模式（选定区域 / 屏幕中心）

### 3. 启动检测

点击 **启动检测**。

程序会提示：

```text
请在2秒内切回游戏窗口
```

2 秒后开始检测，并在右上角显示运行状态。

### 4. 暂停 / 继续

点击 **暂停 / 继续**，或按 **F4** 全局热键。

### 5. 停止

点击 **停止**。

---

## 推荐参数

### 检测参数

| 参数 | 推荐值 | 说明 |
|------|--------:|------|
| 检测频率 | `500Hz` | 屏幕检测循环频率 |
| 触发冷却 | `30ms` | 防止重复触发 |

### AI 模型参数

| 参数 | 推荐值 | 说明 |
|------|--------:|------|
| 推理设备 | `CPU` | 默认 CPU，GPU 需安装 CUDA |
| 预判延迟 | `20ms` | 接近判定区时提前触发的时间 |
| CPU 线程 | `4` | ONNX 推理线程数 |
| 截取模式 | `选定区域` | 或屏幕中心（需 1080p） |

完整配置示例：

```json
{
  "version": "3.0",
  "region": {
    "left": 880,
    "top": 458,
    "width": 160,
    "height": 160
  },
  "params": {
    "target_hz": 500,
    "cooldown_ms": 30
  },
  "capture": {
    "backend": "mss",
    "obs_camera_index": 0
  },
  "input": {
    "method": "pydirectinput",
    "pico_usb_port": null
  },
  "ai": {
    "model": "model.onnx",
    "device": "cpu",
    "ante_ms": 20,
    "threads": 4,
    "capture_mode": "region"
  }
}
```

---

## 调试建议

### AI 模型 FPS 过低

- 使用性能模式电源设置
- 在任务管理器中将程序设为高优先级
- 关闭后台应用，降低游戏画质
- 增加 CPU 线程数
- 使用 GPU 推理

### 触发偏早或偏晚

调节 **预判延迟**：

- 偏早：降低数值，例如 `20ms → 10ms → 0ms`
- 偏晚：提高数值，例如 `20ms → 30ms → 40ms`

### 触发的是 Good 而非 Great

- 确保游戏和 AI 模型 FPS 都在 60 以上
- 检查网络延迟（ping）
- 禁用游戏滤镜 / Reshade / VSync / FSR
- 降低预判延迟值

### 游戏没有响应 Space

如果 GUI 中 **触发次数增加**，但游戏没有反应：

1. 确保游戏窗口在前台。
2. 使用 `run_qte.bat` 管理员权限启动。
3. 确认游戏 QTE 绑定包含 `Space`。
4. 避免独占全屏，建议无边框窗口或窗口化。

---

## 图像获取与输入方式

### 图像获取

项目支持两种采集方式：

#### MSS

默认方式，直接截取用户框选区域：

```text
mss.grab(region)
→ 缩放到 224×224
→ ONNX 模型推理
→ 11 类分类判定
```

优点是延迟低、配置简单；缺点是少数游戏/显示模式可能阻止或影响截屏。

#### OBS 虚拟摄像头

当 MSS 截屏被游戏阻止时，可以切换到 OBS 采集：

```text
OBS 捕获游戏画面
→ 启动 OBS 虚拟摄像头
→ 工具读取虚拟摄像头画面
→ 按 region 坐标裁剪并缩放到 224×224
→ ONNX 模型推理
→ 11 类分类判定
```

OBS 使用步骤：

1. **配置OBS画布和虚拟摄像头**
   - 在 OBS 中添加游戏捕获、窗口捕获或显示器捕获
   - 设置画布分辨率为 1920×1080（设置 → 视频 → 基础画布分辨率）
   - **重要：设置虚拟摄像头输出分辨率为 1920×1080**
     - OBS 28+: 工具 → 虚拟摄像头 → 配置 → 输出分辨率
     - 如果找不到设置，请查看 `OBS配置指南.md`

2. **启动虚拟摄像头**
   - 在 OBS 中点击 **启动虚拟摄像头**

3. **在程序中配置**
   - 在工具 GUI 的 **图像采集方式** 中选择 `OBS 虚拟摄像头`
   - 点击 **🔍 扫描** 按钮查找可用摄像头
   - 根据扫描结果选择正确的 `OBS编号`（通常是 0 或 1）

注意：
- OBS 采集通常帧率低于 MSS，延迟也更高，但兼容性更好
- **OBS画布分辨率** 和 **虚拟摄像头输出分辨率** 是两个不同的设置，都需要设置为 1920×1080
- 如果 MSS 模式能正常工作，优先使用 MSS 模式

### 输入方式

项目支持两种输入方式：

1. **PyDirectInput 软件输入**：默认方式，通过 Windows API 发送 Space
2. **Pico 2W USB 串口硬件输入**：通过 USB HID 键盘发送，延迟 < 1ms

如需使用 Pico 2W USB 串口，请先安装 `pyserial` 并参考 `docs/PICO_SETUP.md`。

---

## 打包

打包主程序：

```bash
python build.py
```

重新生成初始化器：

```bash
python build_initialize.py
```

---

## 技术架构

### AI 模型

- **架构**：MobileNet V3 Small（编码器-解码器结构）
- **输入**：224×224 RGB 图像
- **输出**：11 类分类概率
- **模型大小**：~6MB（ONNX 格式）
- **推理速度**：~10ms/帧（CPU），120+fps

### 预处理

```text
原始帧 → float32 / 255.0 → HWC 转 CHW → ImageNet 归一化 → (1, 3, 224, 224)
```

归一化参数：

- MEAN = [0.485, 0.456, 0.406]
- STD = [0.229, 0.224, 0.225]

### 模型来源

AI 模型来自 [Manuteaa/dbd_autoSkillCheck](https://github.com/Manuteaa/dbd_autoSkillCheck) 项目，遵循 GPL-3.0 许可证。

---

## 注意事项

- 本工具不会读取游戏内存。
- 本工具不会注入游戏进程。
- 本工具依赖屏幕画面识别，分辨率和窗口模式会影响识别效果。
- 最佳性能需要游戏和 AI 模型 FPS 都在 60 以上。
- 在带反作弊或联网环境中使用自动化工具可能违反游戏服务条款，请自行承担风险。

---

## 致谢

- AI 模型和训练数据来自 [Manuteaa/dbd_autoSkillCheck](https://github.com/Manuteaa/dbd_autoSkillCheck)
- MobileNet V3 Small 架构来自 PyTorch torchvision

---

## 免责声明

本项目仅供学习、研究和单机游戏辅助使用。请勿用于破坏公平性的联网游戏或违反服务条款的场景。作者不对任何账号处罚、封禁、数据损失或其他后果负责。
