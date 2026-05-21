"""
Pico 2W - QTE 硬件输入固件 (USB 串口版本)
通过 USB 串口接收命令，无需 BLE

连接方式：
- USB 连接到 PC（同时用于串口通信和 HID 输入）

命令协议：
- 0x01: 发送 Space 键
- 0xFF: 心跳检测
"""

import time
import board
import digitalio
import usb_cdc
import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode

print("=" * 50)
print("Pico QTE 硬件输入固件 (USB 串口版)")
print("=" * 50)

# 初始化 LED
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
led.value = False

# LED 闪烁 3 次表示启动
for _ in range(3):
    led.value = True
    time.sleep(0.2)
    led.value = False
    time.sleep(0.2)

print("[1/2] LED 测试完成")

# 初始化 USB HID 键盘
try:
    keyboard = Keyboard(usb_hid.devices)
    print("[2/2] USB HID 键盘初始化成功")
except Exception as e:
    print(f"[2/2] USB HID 初始化失败: {e}")
    while True:
        led.value = not led.value
        time.sleep(0.1)

# 获取串口对象
serial = usb_cdc.data

print("\n" + "=" * 50)
print("✓ 初始化完成！")
print("=" * 50)
print("设备信息:")
print("  - USB HID: 已就绪")
print(f"  - 串口: {serial}")
print("\n等待 PC 端连接...")
print("LED 将在收到命令时快速闪烁")
print("=" * 50 + "\n")

# 命令定义
CMD_SPACE = 0x01
CMD_PING = 0xFF

# 统计信息
command_count = 0
last_command_time = 0

# 主循环
while True:
    # 检查是否有数据可读
    if serial and serial.in_waiting > 0:
        try:
            # 读取一个字节
            data = serial.read(1)

            if data:
                cmd = data[0]

                # LED 快闪表示收到命令
                led.value = True

                if cmd == CMD_SPACE:
                    # 发送 Space 键
                    keyboard.press(Keycode.SPACE)
                    keyboard.release(Keycode.SPACE)

                    command_count += 1
                    now = time.monotonic_ns() // 1_000_000

                    if last_command_time > 0:
                        interval = now - last_command_time
                        if interval < 100:
                            print(f"[快速触发] 间隔: {interval}ms")

                    last_command_time = now

                elif cmd == CMD_PING:
                    # 心跳响应
                    if serial:
                        serial.write(b"\xFF")

                led.value = False

        except Exception as e:
            print(f"[ERROR] 处理命令失败: {e}")
            led.value = False

    # 短暂休眠，降低 CPU 占用
    time.sleep(0.001)  # 1ms