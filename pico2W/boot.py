"""
boot.py - CircuitPython USB 配置
启用 USB HID 键盘和串口数据通道
"""

import usb_cdc
import usb_hid

# 启用 USB CDC 数据通道（用于串口通信）
usb_cdc.enable(console=True, data=True)

# 启用 USB HID（键盘、鼠标等）
usb_hid.enable((usb_hid.Device.KEYBOARD,))

print("[boot.py] USB HID 和 CDC 已启用")
