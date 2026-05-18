"""
Pico 2W USB 串口通信模块

使用 USB 串口与 Pico 2W 通信，发送按键触发信号。
优化目标：最低延迟（< 1ms）
"""

import serial
import serial.tools.list_ports
import time
from typing import Optional, Callable
from collections import deque


class PicoUSBSender:
    """
    Pico 2W USB 串口发送器

    使用 USB CDC (串口) 与 Pico 2W 通信
    发送单字节命令以最小化延迟
    """

    # 命令定义（单字节，最小延迟）
    CMD_SPACE = b'\x01'  # 发送Space键
    CMD_PING = b'\xFF'   # 心跳检测

    def __init__(self):
        self.serial_port: Optional[serial.Serial] = None
        self.connected = False
        self.port_name: Optional[str] = None

        # 性能统计
        self.send_count = 0
        self.send_errors = 0
        self.latency_samples = deque(maxlen=100)

        # 回调函数
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None

    def scan_devices(self) -> list:
        """扫描可用的 Pico 串口设备"""
        print("[INFO] 扫描 USB 串口设备...")
        ports = serial.tools.list_ports.comports()

        pico_devices = []
        pico_ports = []

        # 先找出所有 Pico 设备
        for port in ports:
            # Raspberry Pi Pico VID = 0x239a
            if port.vid == 0x239a:
                pico_ports.append(port)

        # Pico 有两个 COM 口：Console 和 Data
        # 我们需要 Data 口（通常是第二个）
        if len(pico_ports) >= 2:
            # 使用第二个端口（Data 口）
            data_port = pico_ports[1]
            pico_devices.append({
                'port': data_port.device,
                'description': f"{data_port.description} (CircuitPython CDC data)",
                'manufacturer': data_port.manufacturer,
                'vid': data_port.vid,
                'pid': data_port.pid,
            })
            print(f"  找到: {data_port.device} - {data_port.description} (Data 口)")
        elif len(pico_ports) == 1:
            # 只有一个端口，可能是旧固件或配置问题
            port = pico_ports[0]
            pico_devices.append({
                'port': port.device,
                'description': port.description,
                'manufacturer': port.manufacturer,
                'vid': port.vid,
                'pid': port.pid,
            })
            print(f"  找到: {port.device} - {port.description}")
            print(f"  [警告] 只找到 1 个 COM 口，应该有 2 个（Console 和 Data）")

        return pico_devices

    def connect(self, port: str, baudrate: int = 115200) -> bool:
        """连接到 Pico 串口"""
        try:
            print(f"[INFO] 连接到 {port}...")

            # 打开串口
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=0.1,  # 100ms 超时
                write_timeout=0.1
            )

            # 等待串口稳定
            time.sleep(0.5)

            # 清空缓冲区
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()

            # 发送心跳测试连接
            self.serial_port.write(self.CMD_PING)
            time.sleep(0.1)

            self.connected = True
            self.port_name = port
            print(f"[成功] 已连接到 {port}")

            if self.on_connected:
                self.on_connected()

            return True

        except Exception as e:
            print(f"[ERROR] 连接失败: {e}")
            self.connected = False
            if self.serial_port:
                try:
                    self.serial_port.close()
                except:
                    pass
                self.serial_port = None
            return False

    def disconnect(self):
        """断开连接"""
        if self.serial_port:
            try:
                self.serial_port.close()
            except:
                pass
            self.serial_port = None

        self.connected = False
        print("[INFO] 已断开 Pico USB 连接")

        if self.on_disconnected:
            self.on_disconnected()

    def send_space(self) -> bool:
        """
        发送 Space 键命令

        这是最关键的方法，需要最低延迟
        """
        if not self.connected or not self.serial_port:
            return False

        try:
            start_time = time.perf_counter()

            # 写入命令
            self.serial_port.write(self.CMD_SPACE)

            latency = (time.perf_counter() - start_time) * 1000
            self.latency_samples.append(latency)
            self.send_count += 1

            return True

        except Exception as e:
            self.send_errors += 1
            print(f"[ERROR] 发送命令失败: {e}")
            # 连接可能断开
            self.connected = False
            return False

    def get_stats(self) -> dict:
        """获取性能统计"""
        avg_latency = sum(self.latency_samples) / len(self.latency_samples) if self.latency_samples else 0
        max_latency = max(self.latency_samples) if self.latency_samples else 0

        return {
            'connected': self.connected,
            'port': self.port_name,
            'send_count': self.send_count,
            'send_errors': self.send_errors,
            'avg_latency_ms': round(avg_latency, 2),
            'max_latency_ms': round(max_latency, 2),
        }

    def __del__(self):
        """清理资源"""
        self.disconnect()


# 全局单例
_pico_sender: Optional[PicoUSBSender] = None


def get_pico_usb_sender() -> PicoUSBSender:
    """获取全局 Pico USB 发送器单例"""
    global _pico_sender
    if _pico_sender is None:
        _pico_sender = PicoUSBSender()
    return _pico_sender
