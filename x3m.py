import cv2
import numpy as np
import mss
import pydirectinput
import time
import threading
import sys

_IW = sys.platform == "win32"

if _IW:
    import ctypes
    _wm = ctypes.windll.winmm
    _wm.timeBeginPeriod(1)
else:
    print(f"[WARN] 当前系统为 {sys.platform}，pydirectinput 仅支持 Windows。")
    print("[WARN] 响应功能将不可用。")

class _E7:
    _PI = 0.033

    def __init__(self):
        self._rn = False
        self._pd = False
        self._th = None
        self._hz = 500
        self._cd = 30
        self._im = "pydirectinput"
        self._pc = None
        self._lk = threading.Lock()
        self._tc = 0
        self._fc = 0
        self._hc = 0
        self._lt = 0.0
        self._lm = 0.0
        self._lx = 0.0
        self._lc = 0
        self._lh = [0] * 64
        self._hb = 0.5
        self._pl = threading.Lock()
        self._pv = None
        self._amp = "models/model.onnx"
        self._dl = 0
        self._act = 0.0
        self._ath = 4
        self._ad = None
        self._alp = 0
        self._ald = ""
        self._alr = {}
        self._alh = False
        self._alc = 0.0

    def _t0(self) -> bool:
        _now = time.perf_counter()
        _cd = self._cd / 1000.0
        if _now - self._lt < _cd:
            return False
        if not _IW:
            print("[WARN] 非 Windows 系统，跳过响应")
            return False
        try:
            if self._im == "pico2w":
                if self._pc:
                    _ok = self._pc._s4()
                    if not _ok:
                        print("[WARN] 硬件发送失败")
                        return False
                else:
                    print("[ERROR] 硬件未连接")
                    return False
            else:
                pydirectinput.press('space')
        except Exception as _e:
            print(f"[ERROR] Trigger failed: {_e}")
            return False
        self._lt = _now
        with self._lk:
            self._tc += 1
        return True

    def _l0(self):
        from v9d import _D3, _i1
        if not _i1():
            raise RuntimeError("onnxruntime 未安装，请运行: pip install onnxruntime")
        self._ad = _D3(model_path=self._amp, num_threads=self._ath)
        _pr = self._ad._c0()
        print(f"[INFO] 配置已加载: {self._amp}")
        print(f"[INFO] 计算设备: {_pr}")

    def _u0(self):
        if self._ad is not None:
            self._ad._c1()
            self._ad = None

    def _c0(self, _sct) -> np.ndarray:
        try:
            _mn = _sct.monitors[1]
            _sw = _mn["width"]
            _sh = _mn["height"]
        except (IndexError, KeyError):
            return None
        _cs = 224
        _l = (_sw - _cs) // 2
        _t = (_sh - _cs) // 2
        if _l < 0 or _t < 0:
            return None
        _rr = {"left": _l, "top": _t, "width": _cs, "height": _cs}
        _sg = _sct.grab(_rr)
        _rw = np.frombuffer(_sg.raw, dtype=np.uint8).reshape((_cs, _cs, 4))
        return _rw[:, :, [2, 1, 0]].copy()

    def _r0(self, enable_preview: bool = True):
        self._rn = True
        self._pd = False
        try:
            self._l0()
        except Exception as _e:
            print(f"[ERROR] 配置加载失败: {_e}")
            self._rn = False
            return
        _iv = 1.0 / self._hz
        _lpt = 0.0
        _lht = 0.0
        _hcd = 0.5
        with mss.mss() as _sct:
            while self._rn:
                if self._pd:
                    time.sleep(0.05)
                    continue
                _t0 = time.perf_counter()
                _fr = self._c0(_sct)
                if _fr is None:
                    time.sleep(0.01)
                    continue
                _sh, _pd, _dc, _pb, _cf = self._ad._p1(_fr, self._act)
                _now = time.perf_counter()
                _tg = False
                if _sh and (_now - _lht) >= _hcd:
                    if self._dl > 0:
                        time.sleep(self._dl / 1000.0)
                    _tg = self._t0()
                    if _tg:
                        _lht = time.perf_counter()
                with self._lk:
                    self._fc += 1
                    if _sh:
                        self._hc += 1
                    self._alp = _pd
                    self._ald = _dc
                    self._alr = dict(_pb)
                    self._alh = _sh
                    self._alc = _cf
                if enable_preview and (_t0 - _lpt) >= self._PI:
                    _pv = self._d0(_fr, _pd, _dc, _pb, _sh, _tg)
                    with self._pl:
                        self._pv = _pv
                    _lpt = _t0
                _el = time.perf_counter() - _t0
                with self._lk:
                    _lms = _el * 1000
                    self._lc += 1
                    _dl = _lms - self._lm
                    self._lm += _dl / self._lc
                    if _lms > self._lx:
                        self._lx = _lms
                    _bk = int(_lms / self._hb)
                    if _bk < 64:
                        self._lh[_bk] += 1
                _sl = _iv - _el
                if _sl > 0.002:
                    time.sleep(_sl - 0.001)
                while time.perf_counter() - _t0 < _iv:
                    pass

    def _d0(self, _fr, _pd: int, _dc: str, _pb: dict, _sh: bool, _tg: bool) -> np.ndarray:
        _dp = cv2.cvtColor(_fr, cv2.COLOR_RGB2BGR)
        _dp = cv2.resize(_dp, (224, 224), interpolation=cv2.INTER_NEAREST)
        _cl = (0, 255, 0) if _tg else ((0, 255, 255) if _sh else (200, 200, 200))
        _st = f"{_dc} {'HIT!' if _sh else ''} {'[TRIG]' if _tg else ''}"
        cv2.putText(_dp, _st, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, _cl, 1)
        if _pb:
            _tp = max(_pb, key=_pb.get)
            _tv = _pb[_tp]
            cv2.putText(_dp, f"{_tv:.1%}", (5, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)
        if _tg:
            cv2.rectangle(_dp, (0, 0), (223, 223), (0, 255, 0), 3)
        return cv2.cvtColor(_dp, cv2.COLOR_BGR2RGB)

    @property
    def _p0(self):
        with self._pl:
            return self._pv

    @property
    def _p1(self):
        with self._lk:
            return [self._lm] if self._lc > 0 else []

    def _c1(self) -> float:
        if self._lc == 0:
            return 0.0
        _th = self._lc * 0.99
        _cu = 0
        for _i, _c in enumerate(self._lh):
            _cu += _c
            if _cu >= _th:
                return (_i + 0.5) * self._hb
        return 63.5 * self._hb

    def _g0(self) -> dict:
        with self._lk:
            if self._lc == 0:
                return {}
            _alm = self._lm
            _alx = self._lx
            _hc = self._hc
            _fc = self._fc
            _tc = self._tc
            _ald = self._ald
            _alr = dict(self._alr)
            _alc = self._alc
        _hr = (_hc / _fc * 100) if _fc > 0 else 0.0
        return {
            "avg_latency": f"{_alm:.2f}ms",
            "p99_latency": f"{self._c1():.2f}ms",
            "max_latency": f"{_alx:.2f}ms",
            "trigger_count": _tc,
            "frame_count": _fc,
            "hit_rate": f"{_hr:.1f}%",
            "ai_prediction": _ald,
            "ai_confidence": f"{_alc:.1%}",
            "ai_provider": self._ad._c0() if self._ad else "---",
        }

    def _s1(self, preview: bool = True):
        if self._rn:
            return
        if self._th and self._th.is_alive():
            return
        self._th = threading.Thread(target=self._r0, args=(preview,), daemon=True)
        self._th.start()

    def _s2(self):
        self._rn = False
        self._pd = False
        with self._lk:
            self._lm = 0.0
            self._lx = 0.0
            self._lc = 0
            self._lh = [0] * 64
            self._hc = 0
        if self._th and self._th.is_alive():
            self._th.join(timeout=2.0)
        self._u0()

    def _t1(self) -> bool:
        self._pd = not self._pd
        return self._pd