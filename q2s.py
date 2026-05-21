import serial
import serial.tools.list_ports
import time
from typing import Optional, Callable
from collections import deque


class _P5:
    _C1 = b'\x01'
    _C2 = b'\xFF'

    def __init__(self):
        self._s0: Optional[serial.Serial] = None
        self._c0 = False
        self._p0: Optional[str] = None
        self._n0 = 0
        self._n1 = 0
        self._n2 = deque(maxlen=100)
        self._f0: Optional[Callable] = None
        self._f1: Optional[Callable] = None

    def _s3(self) -> list:
        print("[INFO] 扫描 USB 串口设备...")
        _p1 = serial.tools.list_ports.comports()
        print(f"[DEBUG] 找到 {len(_p1)} 个串口设备:")
        for _p in _p1:
            _v = _p.vid if _p.vid else 0
            _d = _p.pid if _p.pid else 0
            print(f"  - {_p.device}: VID=0x{_v:04x}, PID=0x{_d:04x}, {_p.description}")
        _r0 = []
        _r1 = []
        for _p in _p1:
            if _p.vid == 0x239a or _p.vid == 0x2e8a:
                _r1.append(_p)
                print(f"[DEBUG] 识别为 Pico: {_p.device} (VID=0x{_p.vid:04x})")
        print(f"[INFO] 找到 {len(_r1)} 个 Pico COM 口")
        if len(_r1) >= 2:
            _r1.sort(key=lambda p: p.device)
            _cp = _r1[0]
            _dp = _r1[1]
            _r0.append({
                'port': _dp.device,
                'description': f"{_dp.description} (Data 口 - 通信用)",
                'manufacturer': _dp.manufacturer,
                'vid': _dp.vid,
                'pid': _dp.pid,
            })
            print(f"  [OK] Console 口: {_cp.device} (跳过)")
            print(f"  [OK] Data 口: {_dp.device} (自动选择)")
        elif len(_r1) == 1:
            _p = _r1[0]
            _r0.append({
                'port': _p.device,
                'description': f"{_p.description} (仅1个COM口)",
                'manufacturer': _p.manufacturer,
                'vid': _p.vid,
                'pid': _p.pid,
            })
            print(f"  找到: {_p.device} - {_p.description}")
            print(f"  [警告] 只找到 1 个 Pico COM 口，正常应该有 2 个（Console 和 Data）")
            print(f"  [提示] 如果连接失败，请检查 Pico 固件是否正确配置")
        return _r0

    def _c2(self, port: str, baudrate: int = 115200) -> bool:
        try:
            print(f"[INFO] 连接到 {port}...")
            self._s0 = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=0.1,
                write_timeout=0.1
            )
            time.sleep(0.5)
            self._s0.reset_input_buffer()
            self._s0.reset_output_buffer()
            self._s0.write(self._C2)
            time.sleep(0.1)
            self._c0 = True
            self._p0 = port
            print(f"[成功] 已连接到 {port}")
            if self._f0:
                self._f0()
            return True
        except Exception as _e:
            print(f"[ERROR] 连接失败: {_e}")
            self._c0 = False
            if self._s0:
                try:
                    self._s0.close()
                except:
                    pass
                self._s0 = None
            return False

    def _d0(self):
        if self._s0:
            try:
                self._s0.close()
            except:
                pass
            self._s0 = None
        self._c0 = False
        print("[INFO] 已断开 Pico USB 连接")
        if self._f1:
            self._f1()

    def _s4(self) -> bool:
        if not self._c0 or not self._s0:
            return False
        try:
            _t0 = time.perf_counter()
            self._s0.write(self._C1)
            _l0 = (time.perf_counter() - _t0) * 1000
            self._n2.append(_l0)
            self._n0 += 1
            return True
        except Exception as _e:
            self._n1 += 1
            print(f"[ERROR] 发送命令失败: {_e}")
            self._c0 = False
            return False

    def _g0(self) -> dict:
        _a0 = sum(self._n2) / len(self._n2) if self._n2 else 0
        _m0 = max(self._n2) if self._n2 else 0
        return {
            'connected': self._c0,
            'port': self._p0,
            'send_count': self._n0,
            'send_errors': self._n1,
            'avg_latency_ms': round(_a0, 2),
            'max_latency_ms': round(_m0, 2),
        }

    def __del__(self):
        self._d0()


_g3: Optional[_P5] = None


def _g2() -> _P5:
    global _g3
    if _g3 is None:
        _g3 = _P5()
    return _g3
