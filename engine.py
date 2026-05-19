"""
QTE Auto Tool - Core Engine (v3.0)
AI-powered screen analysis and auto-trigger system.

Design Philosophy:
- AI model (ONNX) detection: MobileNet V3 Small, 11-class skill check classification
- Supports all QTE types: repair-heal, full-white, full-black, wiggle, special perks
- GPU-first inference (CUDA/DirectML, auto-fallback to CPU)
- Ante-frontier hit delay
- Thread-safe shared state with Lock protection
- Decoupled preview generation (~30Hz) from detection loop
"""

import cv2
import numpy as np
import mss
import pydirectinput
import time
import threading
import sys
from collections import deque


def _check_platform():
    if sys.platform != "win32":
        print(f"[WARN] 当前系统为 {sys.platform}，pydirectinput 仅支持 Windows。")
        print("[WARN] 按键模拟功能将不可用。")
        return False
    return True


_IS_WINDOWS = _check_platform()


class QTEEngine:
    """
    AI-powered detection engine for QTE automation.

    Uses ONNX Runtime with MobileNet V3 Small to classify skill check frames
    into 11 categories and automatically trigger great skill checks.

    Features:
    - ONNX model inference with GPU-first (CUDA/DirectML/CPU fallback)
    - 11-class skill check classification (all QTE types)
    - Ante-frontier hit delay for timing optimization
    - Flexible capture: MSS / OBS virtual camera
    - Thread-safe shared state with Lock protection
    - Decoupled preview generation (~30Hz) from detection loop
    """

    PREVIEW_INTERVAL = 0.033

    def __init__(self):
        self.region = None
        self.running = False
        self.paused = False
        self.thread = None

        self.target_hz = 500
        self.cooldown_ms = 30

        self.capture_backend = "mss"
        self.obs_camera_index = 0

        self.input_method = "pydirectinput"
        self.pico_connection = None

        self._lock = threading.Lock()
        self._latency_log = deque(maxlen=500)
        self._trigger_count = 0
        self._frame_count = 0
        self._hit_log = deque(maxlen=100)
        self._last_trigger_time = 0.0

        self._latency_sum = 0.0
        self._latency_max = 0.0
        self._latency_count = 0

        self._preview_lock = threading.Lock()
        self._latest_preview = None

        self._obs_capture = None

        self.ai_model_path = "models/model.onnx"
        self.ai_hit_ante_ms = 20
        self.ai_capture_mode = "region"
        self._ai_detector = None
        self._ai_last_pred = 0
        self._ai_last_desc = ""
        self._ai_last_probs = {}
        self._ai_last_hit = False

    def set_region(self, left: int, top: int, width: int, height: int):
        self.region = {
            "left": int(left),
            "top": int(top),
            "width": int(width),
            "height": int(height)
        }

    def trigger(self) -> bool:
        now = time.perf_counter()
        cooldown = self.cooldown_ms / 1000.0
        if now - self._last_trigger_time < cooldown:
            return False
        if not _IS_WINDOWS:
            print("[WARN] 非 Windows 系统，跳过按键模拟")
            return False

        try:
            if self.input_method == "pico2w":
                if self.pico_connection:
                    success = self.pico_connection.send_space()
                    if not success:
                        print("[WARN] Pico 2W发送失败")
                        return False
                else:
                    print("[ERROR] Pico 2W未连接")
                    return False
            else:
                pydirectinput.press('space')

        except Exception as e:
            print(f"[ERROR] Trigger failed: {e}")
            return False

        self._last_trigger_time = now
        with self._lock:
            self._trigger_count += 1
        return True

    def _load_ai_model(self):
        from ai_detector import AIDetector, is_onnxruntime_available
        if not is_onnxruntime_available():
            raise RuntimeError("onnxruntime 未安装，请运行: pip install onnxruntime")
        self._ai_detector = AIDetector(self.ai_model_path)
        provider = self._ai_detector.check_provider()
        print(f"[INFO] AI 模型已加载: {self.ai_model_path}")
        print(f"[INFO] 推理设备: {provider}")

    def _unload_ai_model(self):
        if self._ai_detector is not None:
            self._ai_detector.cleanup()
            self._ai_detector = None

    def _capture_frame(self, sct) -> np.ndarray:
        if self.capture_backend == "obs":
            return self._capture_frame_obs()

        if self.ai_capture_mode == "center":
            try:
                monitor = sct.monitors[1]
                screen_w = monitor["width"]
                screen_h = monitor["height"]
            except (IndexError, KeyError):
                return None
            crop_size = 224
            left = (screen_w - crop_size) // 2
            top = (screen_h - crop_size) // 2
            if left < 0 or top < 0:
                return None
            region = {"left": left, "top": top, "width": crop_size, "height": crop_size}
            shot = sct.grab(region)
            raw = np.frombuffer(shot.raw, dtype=np.uint8).reshape((crop_size, crop_size, 4))
            return raw[:, :, [2, 1, 0]].copy()
        else:
            if self.region is None:
                return None
            shot = sct.grab(self.region)
            h, w = self.region["height"], self.region["width"]
            raw = np.frombuffer(shot.raw, dtype=np.uint8).reshape((h, w, 4))
            frame_rgb = raw[:, :, [2, 1, 0]].copy()
            return cv2.resize(frame_rgb, (224, 224), interpolation=cv2.INTER_LINEAR)

    def _capture_frame_obs(self) -> np.ndarray:
        if self._obs_capture is None:
            backend = cv2.CAP_DSHOW if sys.platform == "win32" else 0
            self._obs_capture = cv2.VideoCapture(self.obs_camera_index, backend)
            if not self._obs_capture.isOpened():
                print(f"[ERROR] 无法打开 OBS 虚拟摄像头")
                self._obs_capture.release()
                self._obs_capture = None
                return None

        ok, frame = self._obs_capture.read()
        if not ok or frame is None:
            return None

        if self.ai_capture_mode == "center":
            h, w = frame.shape[:2]
            crop_size = 224
            left = (w - crop_size) // 2
            top = (h - crop_size) // 2
            if left < 0 or top < 0:
                return None
            return frame[top:top + crop_size, left:left + crop_size, ::-1].copy()
        else:
            if self.region is None:
                return None
            left = self.region["left"]
            top = self.region["top"]
            width = self.region["width"]
            height = self.region["height"]
            if top + height > frame.shape[0] or left + width > frame.shape[1]:
                return None
            cropped = frame[top:top + height, left:left + width, ::-1]
            return cv2.resize(cropped, (224, 224), interpolation=cv2.INTER_LINEAR)

    def run_loop(self, enable_preview: bool = True):
        self.running = True
        self.paused = False

        try:
            self._load_ai_model()
        except Exception as e:
            print(f"[ERROR] AI模型加载失败: {e}")
            self.running = False
            return

        interval = 1.0 / self.target_hz
        last_preview_time = 0.0
        last_hit_time = 0.0
        hit_cooldown = 0.5

        with mss.mss() as sct:
            while self.running:
                if self.paused:
                    time.sleep(0.05)
                    continue

                t0 = time.perf_counter()

                frame = self._capture_frame(sct)
                if frame is None:
                    time.sleep(0.01)
                    continue

                should_hit, pred, desc_cn, probs_dict, is_ante = self._ai_detector.predict(frame)

                now = time.perf_counter()
                triggered = False

                if should_hit and (now - last_hit_time) >= hit_cooldown:
                    if is_ante and self.ai_hit_ante_ms > 0:
                        time.sleep(self.ai_hit_ante_ms / 1000.0)
                    triggered = self.trigger()
                    if triggered:
                        last_hit_time = time.perf_counter()

                with self._lock:
                    self._frame_count += 1
                    self._hit_log.append(1 if should_hit else 0)
                    self._ai_last_pred = pred
                    self._ai_last_desc = desc_cn
                    self._ai_last_probs = dict(probs_dict)
                    self._ai_last_hit = should_hit

                if enable_preview and (t0 - last_preview_time) >= self.PREVIEW_INTERVAL:
                    preview = self._draw_preview(frame, pred, desc_cn, probs_dict, should_hit, triggered)
                    with self._preview_lock:
                        self._latest_preview = preview
                    last_preview_time = t0

                elapsed = time.perf_counter() - t0
                with self._lock:
                    latency_ms = elapsed * 1000
                    self._latency_log.append(latency_ms)
                    self._latency_sum += latency_ms
                    self._latency_max = max(self._latency_max, latency_ms)
                    self._latency_count += 1

                sleep = interval - elapsed
                if sleep > 0:
                    time.sleep(sleep)

    def _draw_preview(self, frame_rgb: np.ndarray, pred: int, desc_cn: str,
                      probs_dict: dict, should_hit: bool, triggered: bool) -> np.ndarray:
        display = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        display = cv2.resize(display, (224, 224), interpolation=cv2.INTER_NEAREST)

        color = (0, 255, 0) if triggered else ((0, 255, 255) if should_hit else (200, 200, 200))
        status = f"{desc_cn} {'HIT!' if should_hit else ''} {'[TRIG]' if triggered else ''}"
        cv2.putText(display, status, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        if probs_dict:
            top_pred = max(probs_dict, key=probs_dict.get)
            top_prob = probs_dict[top_pred]
            cv2.putText(display, f"{top_prob:.1%}", (5, 40), cv2.FONT_HERSHEY_SIMPLEX,
                        0.4, (150, 150, 150), 1)

        if triggered:
            cv2.rectangle(display, (0, 0), (223, 223), (0, 255, 0), 3)

        return cv2.cvtColor(display, cv2.COLOR_BGR2RGB)

    @property
    def latest_preview(self):
        with self._preview_lock:
            return self._latest_preview

    @property
    def latency_log(self):
        with self._lock:
            return list(self._latency_log)

    def get_stats(self) -> dict:
        with self._lock:
            if self._latency_count == 0:
                return {}
            avg_latency = self._latency_sum / self._latency_count
            max_latency = self._latency_max
            hit_log = list(self._hit_log)
            trigger_count = self._trigger_count
            frame_count = self._frame_count
            latency_log = list(self._latency_log)
            ai_last_desc = self._ai_last_desc
            ai_last_probs = dict(self._ai_last_probs)

        p99_latency = np.percentile(latency_log, 99) if latency_log else 0.0

        return {
            "avg_latency": f"{avg_latency:.2f}ms",
            "p99_latency": f"{p99_latency:.2f}ms",
            "max_latency": f"{max_latency:.2f}ms",
            "trigger_count": trigger_count,
            "frame_count": frame_count,
            "hit_rate": f"{np.mean(hit_log) * 100:.1f}%" if hit_log else "0%",
            "ai_prediction": ai_last_desc,
            "ai_provider": self._ai_detector.check_provider() if self._ai_detector else "---",
        }

    def start(self, preview: bool = True):
        if self.running:
            return
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self.run_loop, args=(preview,),
                                       daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.paused = False
        with self._lock:
            self._latency_sum = 0.0
            self._latency_max = 0.0
            self._latency_count = 0
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        self._unload_ai_model()
        if self._obs_capture is not None:
            self._obs_capture.release()
            self._obs_capture = None

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused
