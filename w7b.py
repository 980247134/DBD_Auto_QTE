import sys
import os
import json
import time
import base64
import threading
import ctypes
from ctypes import wintypes

import cv2
import numpy as np
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit

from x3m import _E7
from q2s import _g2
from v9d import _D3

_app = Flask(__name__)
_app.config["SECRET_KEY"] = "dbd_aqte_w7b"
_sio = SocketIO(_app, cors_allowed_origins="*", async_mode="threading")

_eng = _E7()
_cf = "app_config.json"
_lb = []
_ll = threading.Lock()
_hse = threading.Event()
_hti = None


class _O0:
    def __init__(self, _orig, _lock, _buf):
        self._o = _orig
        self._l = _lock
        self._b = _buf

    def write(self, _t):
        if _t and _t.strip():
            with self._l:
                self._b.append(_t.rstrip())
        self._o.write(_t)
        self._o.flush()

    def flush(self):
        self._o.flush()

    def __getattr__(self, _n):
        return getattr(self._o, _n)


_sys_out = _O0(sys.stdout, _ll, _lb)
sys.stdout = _sys_out


def _f0():
    with _ll:
        _msgs = list(_lb)
        _lb.clear()
    for _m in _msgs:
        _sio.emit("log", {"msg": _m, "ts": time.strftime("%H:%M:%S")})


def _bg():
    while True:
        _sio.sleep(0.1)
        if _eng._rn:
            _pv = _eng._p0
            if _pv is not None:
                try:
                    _enc = cv2.imencode(".jpg", cv2.cvtColor(_pv, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if _enc[0]:
                        _b64 = base64.b64encode(_enc[1].tobytes()).decode("utf-8")
                        _sio.emit("preview", {"data": _b64})
                except Exception:
                    pass
            _st = _eng._g0()
            if _st:
                _st["running"] = _eng._rn
                _st["paused"] = _eng._pd
                _sio.emit("stats", _st)
        else:
            _sio.emit("stats", {"running": False, "paused": False})
        _f0()


@_app.route("/")
def _idx():
    return render_template("index.html")


@_app.route("/api/status")
def _api_status():
    _st = _eng._g0()
    _st["running"] = _eng._rn
    _st["paused"] = _eng._pd
    _st["input_method"] = _eng._im
    _ps = _g2()
    _st["usb_connected"] = _ps._c0
    _st["usb_port"] = _ps._p0
    return jsonify(_st)


@_app.route("/api/models")
def _api_models():
    _ml = _D3._s1()
    return jsonify(_ml)


@_app.route("/api/start", methods=["POST"])
def _api_start():
    if _eng._rn:
        return jsonify({"ok": False, "error": "already running"})
    _d = request.get_json(silent=True) or {}
    _mp = _d.get("model")
    if not _mp:
        return jsonify({"ok": False, "error": "model required"})
    _fp = os.path.join("models", _mp)
    if not os.path.exists(_fp):
        return jsonify({"ok": False, "error": f"model not found: {_fp}"})
    _eng._amp = _fp
    _eng._dl = int(_d.get("delay_ms", 0))
    _eng._act = float(_d.get("confidence", 60)) / 100.0
    _eng._ath = int(_d.get("threads", 4))
    _eng._hz = int(_d.get("target_hz", 120))
    _eng._cd = int(_d.get("cooldown_ms", 20))
    _eng._s1(preview=True)
    return jsonify({"ok": True})


@_app.route("/api/stop", methods=["POST"])
def _api_stop():
    _eng._s2()
    return jsonify({"ok": True})


@_app.route("/api/pause", methods=["POST"])
def _api_pause():
    if not _eng._rn:
        return jsonify({"ok": False, "error": "not running"})
    _pd = _eng._t1()
    return jsonify({"ok": True, "paused": _pd})


@_app.route("/api/config", methods=["GET"])
def _api_config_get():
    if not os.path.exists(_cf):
        return jsonify({"ok": True, "config": None})
    try:
        with open(_cf, "r", encoding="utf-8") as _f:
            _cfg = json.load(_f)
        return jsonify({"ok": True, "config": _cfg})
    except Exception as _e:
        return jsonify({"ok": False, "error": str(_e)})


@_app.route("/api/config", methods=["POST"])
def _api_config_set():
    _cfg = request.get_json(silent=True)
    if not _cfg:
        return jsonify({"ok": False, "error": "no config body"})
    try:
        with open(_cf, "w", encoding="utf-8") as _f:
            json.dump(_cfg, _f, indent=2)
        _ic = _cfg.get("input", {})
        _im = _ic.get("method", "pydirectinput")
        if _im in ("pydirectinput", "pico2w"):
            _eng._im = _im
        _ac = _cfg.get("ai", {})
        _mn = _ac.get("model")
        if _mn:
            _eng._amp = os.path.join("models", _mn)
        _eng._dl = int(_ac.get("delay_ms", 0))
        _eng._act = float(_ac.get("confidence", 60)) / 100.0
        _eng._ath = int(_ac.get("threads", 4))
        _pc = _cfg.get("params", {})
        _eng._hz = int(_pc.get("target_hz", 120))
        _eng._cd = int(_pc.get("cooldown_ms", 20))
        return jsonify({"ok": True})
    except Exception as _e:
        return jsonify({"ok": False, "error": str(_e)})


@_app.route("/api/input_method", methods=["POST"])
def _api_input_method():
    _d = request.get_json(silent=True) or {}
    _m = _d.get("method")
    if _m not in ("pydirectinput", "pico2w"):
        return jsonify({"ok": False, "error": "invalid method"})
    _eng._im = _m
    if _m == "pico2w":
        _ps = _g2()
        if not _ps._c0:
            _eng._pc = _ps
    return jsonify({"ok": True, "method": _m})


@_app.route("/api/scan_usb", methods=["POST"])
def _api_scan_usb():
    try:
        _ps = _g2()
        _dv = _ps._s3()
        return jsonify({"ok": True, "devices": _dv})
    except Exception as _e:
        return jsonify({"ok": False, "error": str(_e)})


@_app.route("/api/connect_usb", methods=["POST"])
def _api_connect_usb():
    _d = request.get_json(silent=True) or {}
    _port = _d.get("port")
    if not _port:
        return jsonify({"ok": False, "error": "port required"})
    try:
        _ps = _g2()
        _ok = _ps._c2(_port)
        if _ok:
            _eng._pc = _ps
            return jsonify({"ok": True, "port": _port})
        else:
            return jsonify({"ok": False, "error": "connection failed"})
    except Exception as _e:
        return jsonify({"ok": False, "error": str(_e)})


@_app.route("/api/disconnect_usb", methods=["POST"])
def _api_disconnect_usb():
    try:
        _ps = _g2()
        _ps._d0()
        _eng._pc = None
        return jsonify({"ok": True})
    except Exception as _e:
        return jsonify({"ok": False, "error": str(_e)})


def _hk():
    global _hti
    if sys.platform != "win32":
        return
    _u32 = ctypes.windll.user32
    _k32 = ctypes.windll.kernel32
    _hti = _k32.GetCurrentThreadId()
    _hid = 0x5154
    _vk = 0x73
    if not _u32.RegisterHotKey(None, _hid, 0, _vk):
        print("[WARN] F4 hotkey register failed")
        return
    print("[INFO] F4 hotkey registered: pause/resume")
    try:
        _msg = wintypes.MSG()
        while not _hse.is_set():
            _res = _u32.GetMessageW(ctypes.byref(_msg), None, 0, 0)
            if _res == 0 or _res == -1:
                break
            if _msg.message == 0x0312 and _msg.wParam == _hid:
                if _eng._rn:
                    _pd = _eng._t1()
                    _sio.emit("stats", {"running": _eng._rn, "paused": _pd})
                    print(f"[INFO] F4: {'paused' if _pd else 'resumed'}")
    finally:
        _u32.UnregisterHotKey(None, _hid)


def _hk_stop():
    if sys.platform != "win32":
        return
    _hse.set()
    if _hti:
        ctypes.windll.user32.PostThreadMessageW(_hti, 0x0012, 0, 0)


@_sio.on("connect")
def _on_connect():
    emit("stats", {"running": _eng._rn, "paused": _eng._pd})


@_sio.on("disconnect")
def _on_disconnect():
    pass


def main():
    import webbrowser
    _ht = threading.Thread(target=_hk, daemon=True)
    _ht.start()
    _sio.start_background_task(_bg)
    webbrowser.open("http://localhost:5000")
    try:
        _sio.run(_app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
    finally:
        _eng._s2()
        _hk_stop()


if __name__ == "__main__":
    main()