"""
QTE Auto Tool - Core Engine (v2.3)
High-performance screen analysis and auto-trigger system.

Design Philosophy:
- Zero config: 480Hz auto-detects pointer speed, no mode switching needed
- Hyperfocus is just speed change: auto-detected like any other speed
- Auto-adaptive prediction: prediction window adjusts based on measured velocity
- Trajectory tracking verification
"""

import cv2
import numpy as np
import mss
import pydirectinput
import time
import threading
import math
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
    Auto-adaptive detection engine for QTE automation.

    Core Innovation:
    The engine measures the actual pointer velocity from position history at 480Hz.
    This eliminates ALL manual configuration — no mode switching, no Hyperfocus toggle.
    Speed changes from any source (different QTE types, Hyperfocus perk, etc.) are
    automatically captured by the real-time velocity measurement.

    Features:
    - 480Hz detection loop with auto velocity measurement
    - BGR direct thresholding (no HSV conversion overhead)
    - Adaptive linear prediction based on measured speed
    - 3x3 neighborhood hit detection for noise immunity
    - Thread-safe shared state with Lock protection
    - Decoupled preview generation (~30Hz) from detection loop
    """

    PREVIEW_INTERVAL = 0.033

    # Speed classification thresholds (pixels/second, approximate)
    # Used only for display labeling, NOT for detection logic
    SPEED_LABELS = [
        (0, 150, "摆动"),
        (150, 280, "治疗"),
        (280, 500, "修复"),
        (500, 9999, "快速"),
    ]

    def __init__(self):
        self.region = None
        self.running = False
        self.paused = False
        self.thread = None

        # Core detection parameters
        self.target_hz = 500
        self.cooldown_ms = 30
        self.predict_ms = 0

        # White zone detection thresholds
        self.white_v_low = 166
        self.white_s_max = 50

        # Red pointer detection thresholds (configurable via GUI)
        self.red_min_r = 180
        self.red_min_delta = 50
        self.red_max_avg = 220
        self.red_saturation = 0.4

        # Game-specific features
        self.capture_backend = "mss"
        self.obs_camera_index = 0
        self.delay_degree = 3
        self.outer_mask_percent = 100
        self.center_mask_percent = 0
        self.qte_stabilize_ms = 80
        self.qte_stabilize_frames = 4

        # OBS image enhancement parameters
        self.obs_enhance_enabled = True
        self.obs_brightness = 15
        self.obs_contrast = 1.2

        # Input method settings
        self.input_method = "pydirectinput"  # "pydirectinput" or "pico2w"
        self.pico_connection = None  # USB 串口连接对象

        # Auto speed detection state
        self._measured_speed = 0.0
        self._speed_samples = deque(maxlen=8)
        self._pointer_angle_samples = deque(maxlen=2)
        self._detected_mode_label = "---"

        # Thread-safe state
        self._lock = threading.Lock()
        self._latency_log = deque(maxlen=500)
        self._trigger_count = 0
        self._frame_count = 0
        self._hit_log = deque(maxlen=100)
        self._last_trigger_time = 0.0

        # Incremental latency stats
        self._latency_sum = 0.0
        self._latency_max = 0.0
        self._latency_count = 0

        self._preview_lock = threading.Lock()
        self._latest_preview = None

        self._sct = None
        self._obs_capture = None
        self._geom_radii = None
        self._geom_angles_float = None
        self._geom_angles_int = None
        self._geom_xs = None
        self._geom_ys = None
        self._roi_mask = None

    def set_region(self, left: int, top: int, width: int, height: int):
        self.region = {
            "left": int(left),
            "top": int(top),
            "width": int(width),
            "height": int(height)
        }
        self._prepare_geometry()

    def _prepare_geometry(self):
        if self.region is None:
            return
        h = self.region['height']
        w = self.region['width']
        ys, xs = np.indices((h, w))
        cx = w / 2
        cy = h / 2
        self._geom_xs = xs
        self._geom_ys = ys
        self._geom_radii = np.hypot(xs - cx, ys - cy).astype(np.float32)
        self._rebuild_roi_mask()
        angles = np.degrees(np.arctan2(cy - ys, xs - cx)) % 360
        self._geom_angles_float = angles.astype(np.float32)
        self._geom_angles_int = self._geom_angles_float.astype(np.int16)

    def _rebuild_roi_mask(self):
        if self.region is None or self._geom_radii is None:
            return
        max_radius = min(self.region['width'], self.region['height']) * 0.5
        outer_radius = max_radius * (self.outer_mask_percent / 100.0)
        center_radius = max_radius * (self.center_mask_percent / 100.0)
        self._roi_mask = (self._geom_radii <= outer_radius) & (self._geom_radii >= center_radius)

    def set_mask_settings(self, outer_percent: int = None, center_percent: int = None):
        if outer_percent is not None:
            self.outer_mask_percent = max(50, min(110, int(outer_percent)))
        if center_percent is not None:
            self.center_mask_percent = max(0, min(70, int(center_percent)))
        self._rebuild_roi_mask()

    def _classify_speed(self, speed: float) -> str:
        """Classify measured speed into a human-readable label (display only)."""
        for lo, hi, label in self.SPEED_LABELS:
            if lo <= speed < hi:
                return label
        return "---"

    def _update_speed_measurement(self, pos_history: deque):
        """
        Measure pointer velocity from position history.
        Uses angular velocity for rotation-based QTE (more accurate than linear px/s).
        Falls back to linear velocity when pointer is too close to center
        to avoid atan2 instability.
        """
        if len(pos_history) < 2 or self.region is None:
            return

        x2, y2, t2 = pos_history[-1]
        x1, y1, t1 = pos_history[-2]
        dt = t2 - t1

        if dt < 0.0005:
            return

        cx = self.region['width'] / 2
        cy = self.region['height'] / 2

        dx1 = x1 - cx
        dy1 = y1 - cy
        dx2 = x2 - cx
        dy2 = y2 - cy
        dist1 = math.hypot(dx1, dy1)
        dist2 = math.hypot(dx2, dy2)

        min_dist_threshold = min(self.region['width'], self.region['height']) * 0.15

        if dist1 < min_dist_threshold or dist2 < min_dist_threshold:
            linear_speed = math.hypot(x2 - x1, y2 - y1) / dt
            angular_speed = linear_speed
        else:
            a1 = math.degrees(math.atan2(-dy1, dx1)) % 360
            a2 = math.degrees(math.atan2(-dy2, dx2)) % 360
            delta = (a2 - a1 + 540) % 360 - 180
            angular_speed = abs(delta / dt)

        self._speed_samples.append(angular_speed)

        if len(self._speed_samples) >= 2:
            recent = list(self._speed_samples)
            weights = list(range(1, len(recent) + 1))
            weighted_sum = sum(r * w for r, w in zip(recent, weights))
            total_weight = sum(weights)
            smoothed_speed = weighted_sum / total_weight
        else:
            smoothed_speed = angular_speed

        with self._lock:
            self._measured_speed = smoothed_speed
            self._detected_mode_label = self._classify_speed(smoothed_speed)

    def _apply_roi_mask(self, frame: np.ndarray) -> np.ndarray:
        if self._roi_mask is not None:
            frame[~self._roi_mask] = 0
        return frame

    def _enhance_obs_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        OBS模式下的图像增强预处理

        目的：补偿OBS虚拟摄像头视频编码导致的颜色失真
        - OBS的YUV编码会让白色(255,255,255)变成淡白色(~240,240,240)
        - 通过提升亮度和对比度，恢复白色区域的可检测性

        性能优化：
        - 使用cv2.convertScaleAbs，这是OpenCV中最快的亮度/对比度调整方法
        - 在裁剪后调用，只处理QTE区域的小图像（通常160x160），性能影响极小

        参数说明：
        - alpha (contrast): 对比度系数，>1增强对比度
        - beta (brightness): 亮度偏移，正值增加亮度
        """
        enhanced = cv2.convertScaleAbs(
            frame,
            alpha=self.obs_contrast,  # 对比度：1.2 = 提升20%
            beta=self.obs_brightness   # 亮度：+15
        )
        return enhanced

    def capture(self, sct) -> np.ndarray:
        if self.region is None:
            return None
        if self.capture_backend == "obs":
            return self.capture_obs()
        shot = sct.grab(self.region)
        h, w = self.region["height"], self.region["width"]
        raw = np.frombuffer(shot.raw, dtype=np.uint8).reshape((h, w, 4))
        frame = raw[:, :, :3].copy()
        return self._apply_roi_mask(frame)

    def test_camera(self, index: int) -> dict:
        """测试指定编号的摄像头是否可用"""
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else 0
        cap = cv2.VideoCapture(index, backend)

        result = {
            'index': index,
            'available': False,
            'name': None,
            'resolution': None,
            'error': None
        }

        if not cap.isOpened():
            result['error'] = '无法打开'
            cap.release()
            return result

        # 尝试读取一帧
        ok, frame = cap.read()
        if not ok or frame is None:
            result['error'] = '无法读取画面'
            cap.release()
            return result

        result['available'] = True
        result['resolution'] = f"{frame.shape[1]}x{frame.shape[0]}"

        # 尝试获取摄像头名称（Windows）
        if sys.platform == "win32":
            try:
                backend_name = cap.getBackendName()
                result['name'] = backend_name
            except:
                pass

        cap.release()
        return result

    def scan_cameras(self, max_index: int = 10) -> list:
        """扫描所有可用的摄像头"""
        print("[INFO] 开始扫描摄像头...")
        cameras = []

        for i in range(max_index):
            result = self.test_camera(i)
            if result['available']:
                cameras.append(result)
                print(f"  [✓] 摄像头 {i}: {result['resolution']}")
            else:
                print(f"  [✗] 摄像头 {i}: {result['error']}")

        print(f"[INFO] 扫描完成，找到 {len(cameras)} 个可用摄像头")
        return cameras

    def capture_obs(self) -> np.ndarray:
        if self._obs_capture is None:
            backend = cv2.CAP_DSHOW if sys.platform == "win32" else 0
            self._obs_capture = cv2.VideoCapture(self.obs_camera_index, backend)
            if not self._obs_capture.isOpened():
                print(f"[ERROR] 无法打开 OBS 虚拟摄像头 (编号 {self.obs_camera_index})")
                print("[提示] 请确保:")
                print("  1. OBS 已启动")
                print("  2. 在 OBS 中点击了'启动虚拟摄像头'")
                print("  3. 尝试其他摄像头编号 (0-5)")
                self._obs_capture.release()
                self._obs_capture = None
                return None

            # 尝试设置虚拟摄像头分辨率为1920x1080
            self._obs_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            self._obs_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

            # 读取一帧检查实际分辨率
            ok, test_frame = self._obs_capture.read()
            if ok and test_frame is not None:
                actual_w = test_frame.shape[1]
                actual_h = test_frame.shape[0]
                print(f"[成功] OBS 虚拟摄像头 (编号 {self.obs_camera_index}) 已连接")
                print(f"[INFO] 虚拟摄像头分辨率: {actual_w}x{actual_h}")

                if actual_w != 1920 or actual_h != 1080:
                    print(f"[警告] OBS 虚拟摄像头分辨率不是 1920x1080")
                    print(f"[提示] 请在 OBS 中设置虚拟摄像头输出分辨率:")
                    print(f"  工具 → 虚拟摄像头 → 输出分辨率 → 1920x1080")
            else:
                print(f"[成功] OBS 虚拟摄像头 (编号 {self.obs_camera_index}) 已连接")

        ok, frame = self._obs_capture.read()
        if not ok or frame is None:
            print(f"[WARN] OBS 摄像头读取失败 (编号 {self.obs_camera_index})")
            return None

        left = self.region["left"]
        top = self.region["top"]
        width = self.region["width"]
        height = self.region["height"]

        # 检查坐标是否超出画面范围
        if top + height > frame.shape[0] or left + width > frame.shape[1]:
            # 只在第一次或每隔一段时间打印一次错误，避免刷屏
            if not hasattr(self, '_obs_error_printed') or not self._obs_error_printed:
                print(f"[ERROR] 监控区域超出 OBS 画面范围")
                print(f"  OBS 虚拟摄像头输出: {frame.shape[1]}x{frame.shape[0]}")
                print(f"  监控区域坐标: left={left}, top={top}, width={width}, height={height}")
                print(f"  需要的最小画面: {left+width}x{top+height}")
                print(f"\n[解决方法]")
                print(f"  方法1 (推荐): 在 OBS 中设置虚拟摄像头输出为 1920x1080")
                print(f"    - OBS 28+: 工具 → 虚拟摄像头 → 配置 → 输出分辨率")
                print(f"    - OBS 27: 需要重启虚拟摄像头并在设置中调整")
                print(f"  方法2: 切换到 MSS 模式重新框选监控区域")
                print(f"  方法3: 使用 OBS 的'窗口投影'功能全屏显示画面")
                self._obs_error_printed = True
            return None

        cropped = frame[top:top + height, left:left + width].copy()

        # OBS模式下进行图像增强，提升白色区域的可检测性
        if self.obs_enhance_enabled:
            cropped = self._enhance_obs_frame(cropped)

        return self._apply_roi_mask(cropped)

    def detect(self, frame: np.ndarray) -> tuple:
        b, g, r = frame[:, :, 0], frame[:, :, 1], frame[:, :, 2]
        ri = r.astype(np.int16)
        gi = g.astype(np.int16)
        bi = b.astype(np.int16)

        red_mask = (
            (ri > self.red_min_r)
            & (ri > gi + self.red_min_delta)
            & (ri > bi + self.red_min_delta)
            & ((ri + gi + bi) < self.red_max_avg * 3)
        )

        min_gb = np.minimum(gi, bi)
        red_mask &= ((ri - min_gb) > (ri * self.red_saturation))

        white_mask = (ri > self.white_v_low) & (gi > self.white_v_low) & (bi > self.white_v_low)

        max_diff = self.white_s_max
        rg_diff = ri - gi
        gb_diff = gi - bi
        rb_diff = ri - bi
        white_mask &= (
            (rg_diff < max_diff) & (rg_diff > -max_diff)
            & (gb_diff < max_diff) & (gb_diff > -max_diff)
            & (rb_diff < max_diff) & (rb_diff > -max_diff)
        )

        return red_mask, white_mask

    def _angle_from_center(self, point: tuple) -> float:
        cx = self.region['width'] / 2
        cy = self.region['height'] / 2
        x, y = point
        return math.degrees(math.atan2(cy - y, x - cx)) % 360

    def _angle_distance(self, a: float, b: float) -> float:
        return abs((a - b + 180) % 360 - 180)

    def _smooth_circular(self, values: np.ndarray, window: int = 7) -> np.ndarray:
        kernel = np.ones(window, dtype=np.float32) / window
        pad = window // 2
        wrapped = np.concatenate([values[-pad:], values, values[:pad]])
        return np.convolve(wrapped, kernel, mode='valid')

    def _angle_segments(self, active: np.ndarray) -> list:
        segments = []
        visited = np.zeros(360, dtype=bool)
        for start in range(360):
            if not active[start] or visited[start]:
                continue
            indices = []
            idx = start
            while active[idx] and not visited[idx]:
                visited[idx] = True
                indices.append(idx)
                idx = (idx + 1) % 360
                if idx == start:
                    break
            segments.append(indices)
        return segments

    def _estimate_ring_radius(self, white_mask: np.ndarray, red_mask: np.ndarray) -> float:
        if self.region is None:
            return 0.0
        mask = white_mask | red_mask
        if mask.sum() < 20:
            return min(self.region['width'], self.region['height']) * 0.4
        radii = self._geom_radii[mask]
        return float(np.percentile(radii, 82))

    def find_pointer(self, red_mask: np.ndarray, ring_radius: float = None, angle: float = None) -> tuple:
        angle = self._find_pointer_angle(red_mask, ring_radius) if angle is None else angle
        if angle is None:
            return None
        point = self._find_pointer_red_pixel(red_mask, ring_radius, angle)
        if point is not None:
            return point
        return None

    def _find_pointer_red_pixel(self, red_mask: np.ndarray, ring_radius: float, angle: float) -> tuple:
        if red_mask.sum() < 3 or ring_radius is None or angle is None:
            return None
        radii = self._geom_radii[red_mask]
        angles = self._geom_angles_float[red_mask]
        xs = self._geom_xs[red_mask]
        ys = self._geom_ys[red_mask]
        angle_distance = np.abs((angles - angle + 180) % 360 - 180)
        near_centerline = angle_distance <= 7
        near_ring = np.abs(radii - ring_radius) <= max(3, min(self.region['width'], self.region['height']) * 0.08)
        candidates = near_centerline & near_ring
        if candidates.sum() == 0:
            candidates = angle_distance <= 10
        if candidates.sum() == 0:
            return None
        scores = np.abs(radii[candidates] - ring_radius) + angle_distance[candidates] * 0.35
        idx = int(np.argmin(scores))
        return (int(xs[candidates][idx]), int(ys[candidates][idx]))

    def _smooth_pointer_angle(self, angle: float) -> float:
        self._pointer_angle_samples.append(angle)
        angles = np.radians(list(self._pointer_angle_samples))
        weights = np.arange(1, len(angles) + 1, dtype=np.float32)
        unit_x = float((np.cos(angles) * weights).sum() / weights.sum())
        unit_y = float((np.sin(angles) * weights).sum() / weights.sum())
        return math.degrees(math.atan2(unit_y, unit_x)) % 360

    def _find_pointer_angle(self, red_mask: np.ndarray, ring_radius: float = None) -> float:
        if red_mask.sum() < 5 or self.region is None:
            return None

        radii = self._geom_radii[red_mask]
        ring_radius = ring_radius or float(np.percentile(radii, 82))
        ring_width = max(4, min(self.region['width'], self.region['height']) * 0.035)
        angles_float = self._geom_angles_float[red_mask]
        angles = self._geom_angles_int[red_mask]

        inner = (radii < ring_radius - ring_width * 1.2) & (radii > ring_radius * 0.18)
        if inner.sum() < 5:
            inner = (radii < ring_radius - ring_width * 0.7) & (radii > ring_radius * 0.15)
        if inner.sum() < 5:
            return None

        inner_radii = radii[inner]
        inner_angles = angles[inner]
        radial_weights = np.clip(ring_radius - inner_radii, 1, None)
        hist = np.bincount(inner_angles, weights=radial_weights, minlength=360).astype(np.float32)
        hist = self._smooth_circular(hist, 7)
        best = int(hist.argmax())
        if hist[best] <= 0:
            return None

        angle_distance = np.abs((angles_float[inner] - best + 180) % 360 - 180)
        shaft = angle_distance <= 8
        if shaft.sum() < 3:
            shaft = angle_distance <= 12
        if shaft.sum() < 3:
            return float(best)

        shaft_angles = angles_float[inner][shaft]
        shaft_radii = inner_radii[shaft]
        shaft_weights = np.clip(ring_radius - shaft_radii, 1, None)
        shaft_weights *= np.clip(1.0 - (np.abs((shaft_angles - best + 180) % 360 - 180) / 12.0), 0.2, 1.0)

        angle = self._fit_pointer_centerline_angle(shaft_angles, shaft_radii, shaft_weights)
        if angle is None:
            unit_x = float((np.cos(np.radians(shaft_angles)) * shaft_weights).sum() / shaft_weights.sum())
            unit_y = float((np.sin(np.radians(shaft_angles)) * shaft_weights).sum() / shaft_weights.sum())
            angle = math.degrees(math.atan2(unit_y, unit_x)) % 360
        return self._smooth_pointer_angle(angle)

    def _fit_pointer_centerline_angle(self, angles: np.ndarray, radii: np.ndarray, weights: np.ndarray) -> float:
        if len(angles) < 3 or weights.sum() <= 0:
            return None
        x = np.cos(np.radians(angles)) * radii
        y = np.sin(np.radians(angles)) * radii
        cx = float(np.average(x, weights=weights))
        cy = float(np.average(y, weights=weights))
        x0 = x - cx
        y0 = y - cy
        w = weights / weights.sum()
        cov_xx = float((w * x0 * x0).sum())
        cov_xy = float((w * x0 * y0).sum())
        cov_yy = float((w * y0 * y0).sum())
        theta = 0.5 * math.atan2(2 * cov_xy, cov_xx - cov_yy)
        dir_x = math.cos(theta)
        dir_y = math.sin(theta)
        if cx * dir_x + cy * dir_y < 0:
            dir_x = -dir_x
            dir_y = -dir_y
        return math.degrees(math.atan2(dir_y, dir_x)) % 360

    def _find_judgement_arcs(self, white_mask: np.ndarray, red_mask: np.ndarray, ring_radius: float = None) -> list:
        if self.region is None:
            return []

        ring_radius = ring_radius or self._estimate_ring_radius(white_mask, red_mask)
        min_dim = min(self.region['width'], self.region['height'])
        ring_width = max(4, min_dim * 0.035)
        candidates = []

        prompt_half_w = self.region['width'] * 0.28
        prompt_half_h = self.region['height'] * 0.13

        if white_mask.sum() < 20:
            return []

        cx = self.region['width'] / 2
        cy = self.region['height'] / 2
        outside_prompt_mask = (np.abs(self._geom_xs - cx) > prompt_half_w) | (np.abs(self._geom_ys - cy) > prompt_half_h)
        mask = white_mask & outside_prompt_mask
        if mask.sum() < 20:
            return []

        radii = self._geom_radii[mask]
        angles = self._geom_angles_int[mask]

        annulus = (radii >= ring_radius - ring_width * 2.6) & (radii <= ring_radius + ring_width * 2.6)
        if annulus.sum() < 20:
            return []

        counts = np.bincount(angles[annulus], minlength=360).astype(np.float32)
        density = self._smooth_circular(counts, 7)
        nonzero = density[density > 0]
        if len(nonzero) == 0:
            return []

        baseline = float(np.percentile(nonzero, 60))
        peak = float(density.max())
        if peak < max(2.2, baseline + 1.2):
            return []

        active = density >= max(baseline * 1.55, baseline + 1.8, peak * 0.46)
        active = self._smooth_circular(active.astype(np.float32), 5) >= 0.45

        for indices in self._angle_segments(active):
            if not (4 <= len(indices) <= 75):
                continue

            weights = density[indices]
            if weights.sum() <= 0:
                continue

            radians = np.radians(indices)
            unit_x = float((np.cos(radians) * weights).sum() / weights.sum())
            unit_y = float((np.sin(radians) * weights).sum() / weights.sum())
            center_angle = math.degrees(math.atan2(unit_y, unit_x)) % 360
            strength = float(weights.sum() - baseline * len(indices))
            if strength <= 0:
                continue

            candidates.append({
                'center_angle': center_angle,
                'span': min(84, max(10, len(indices) + 8)),
                'color': 'white',
                'size': strength,
            })

        candidates.sort(key=lambda arc: arc['size'], reverse=True)
        return candidates[:1]

    def _white_ring_has_all_sectors(self, white_mask: np.ndarray, ring_radius: float) -> bool:
        if self.region is None or ring_radius is None:
            return False
        min_dim = min(self.region['width'], self.region['height'])
        ring_width = max(4, min_dim * 0.035)
        ring_band = white_mask & (self._geom_radii >= ring_radius - ring_width * 2.6) & (self._geom_radii <= ring_radius + ring_width * 2.6)
        if ring_band.sum() < 24:
            return False
        sector_ids = (self._geom_angles_int[ring_band] // 45).astype(np.int16)
        counts = np.bincount(sector_ids, minlength=8)
        return bool(np.count_nonzero(counts[:8] >= 1) >= 7)

    def _check_arc_hit(self, pointer_angle: float, judgement_arcs: list) -> bool:
        if pointer_angle is None or not judgement_arcs:
            return False
        return any(
            self._angle_distance(pointer_angle, (arc['center_angle'] - self.delay_degree) % 360) <= arc['span'] / 2
            for arc in judgement_arcs
        )

    def trigger(self) -> bool:
        now = time.perf_counter()
        cooldown = self.cooldown_ms / 1000.0
        if now - self._last_trigger_time < cooldown:
            return False
        if not _IS_WINDOWS:
            print("[WARN] 非 Windows 系统，跳过按键模拟")
            return False

        # 根据输入方式选择不同的触发方法
        try:
            if self.input_method == "pico2w":
                # 使用Pico 2W硬件输入
                if self.pico_connection:
                    success = self.pico_connection.send_space()
                    if not success:
                        print("[WARN] Pico 2W发送失败")
                        return False
                else:
                    print("[ERROR] Pico 2W未连接")
                    return False
            else:
                # 使用pydirectinput软件输入
                pydirectinput.press('space')

        except Exception as e:
            print(f"[ERROR] Trigger failed: {e}")
            return False

        self._last_trigger_time = now
        with self._lock:
            self._trigger_count += 1
        return True

    def run_loop(self, enable_preview: bool = True):
        self.running = True
        self.paused = False
        interval = 1.0 / self.target_hz

        pos_history = deque(maxlen=8)
        last_preview_time = 0.0
        last_arc_update_time = 0.0
        cached_ring_radius = None
        cached_judgement_arcs = []
        cached_ring_complete = False
        arc_update_interval = 0.025
        qte_seen_since = None
        qte_stable_frames = 0

        with mss.mss() as sct:
            while self.running:
                if self.paused:
                    time.sleep(0.05)
                    continue

                t0 = time.perf_counter()

                frame = self.capture(sct)
                if frame is None:
                    time.sleep(0.01)
                    continue

                red_mask, white_mask = self.detect(frame)
                if cached_ring_radius is None or (t0 - last_arc_update_time) >= arc_update_interval:
                    cached_ring_radius = self._estimate_ring_radius(white_mask, red_mask)
                    cached_judgement_arcs = self._find_judgement_arcs(white_mask, red_mask, cached_ring_radius)
                    cached_ring_complete = self._white_ring_has_all_sectors(white_mask, cached_ring_radius)
                    last_arc_update_time = t0
                ring_radius = cached_ring_radius
                judgement_arcs = cached_judgement_arcs
                pointer_angle = self._find_pointer_angle(red_mask, ring_radius)
                pointer = self.find_pointer(red_mask, ring_radius, pointer_angle)

                qte_visible = cached_ring_complete and bool(judgement_arcs) and pointer is not None
                if qte_visible:
                    if qte_seen_since is None:
                        qte_seen_since = t0
                        qte_stable_frames = 1
                    else:
                        qte_stable_frames += 1
                else:
                    qte_seen_since = None
                    qte_stable_frames = 0
                    pos_history.clear()
                    self._speed_samples.clear()
                    self._pointer_angle_samples.clear()

                qte_stable = (
                    qte_seen_since is not None
                    and (t0 - qte_seen_since) * 1000 >= self.qte_stabilize_ms
                    and qte_stable_frames >= self.qte_stabilize_frames
                )

                hit = False
                triggered = False

                if pointer:
                    now = t0
                    pos_history.append((pointer[0], pointer[1], now))

                    # Auto speed measurement from position history
                    self._update_speed_measurement(pos_history)

                    check_pos = pointer

                    # Adaptive prediction: use measured velocity directly
                    if len(pos_history) >= 2 and self.predict_ms > 0:
                        x1, y1, t1 = pos_history[-2]
                        x2, y2, t2 = pos_history[-1]
                        dt = t2 - t1
                        if dt > 0.0005:
                            vx = (x2 - x1) / dt
                            vy = (y2 - y1) / dt

                            effective_predict_ms = self.predict_ms
                            with self._lock:
                                current_speed = self._measured_speed
                            if self.delay_degree != 0 and current_speed > 0:
                                degree_to_ms = abs(self.delay_degree) / current_speed * 1000.0
                                if self.delay_degree > 0:
                                    effective_predict_ms += degree_to_ms
                                else:
                                    effective_predict_ms -= degree_to_ms
                                effective_predict_ms = max(0, effective_predict_ms)

                            pred_x = int(x2 + vx * (effective_predict_ms / 1000.0))
                            pred_y = int(y2 + vy * (effective_predict_ms / 1000.0))

                            if self.region:
                                pred_x = max(0, min(pred_x, self.region['width'] - 1))
                                pred_y = max(0, min(pred_y, self.region['height'] - 1))

                            check_pos = (pred_x, pred_y)


                    check_angle = self._angle_from_center(check_pos)
                    hit = qte_stable and red_mask[check_pos[1], check_pos[0]] and self._check_arc_hit(check_angle, judgement_arcs)

                    if hit:
                        triggered = self.trigger()
                        if triggered:
                            pos_history.clear()
                            self._speed_samples.clear()
                            self._pointer_angle_samples.clear()

                with self._lock:
                    self._frame_count += 1
                    self._hit_log.append(1 if hit else 0)

                if enable_preview and (t0 - last_preview_time) >= self.PREVIEW_INTERVAL:
                    preview = self._draw_preview(frame, red_mask, white_mask,
                                                 pointer, hit, triggered)
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

    def _draw_preview(self, frame: np.ndarray, red_mask: np.ndarray,
                      white_mask: np.ndarray, pointer: tuple,
                      hit: bool, triggered: bool) -> np.ndarray:
        if self.region is None:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        preview_w = 200
        preview_h = int(preview_w * self.region['height'] / self.region['width'])
        preview_h = max(100, min(preview_h, 300))

        display = cv2.resize(frame, (preview_w, preview_h), interpolation=cv2.INTER_NEAREST)

        combined_mask = np.zeros_like(display)
        red_small = cv2.resize(red_mask.astype(np.uint8) * 255, (preview_w, preview_h),
                               interpolation=cv2.INTER_NEAREST)
        white_small = cv2.resize(white_mask.astype(np.uint8) * 255, (preview_w, preview_h),
                                 interpolation=cv2.INTER_NEAREST)
        combined_mask[red_small > 128] = (0, 0, 255)
        combined_mask[white_small > 128] = (0, 255, 0)

        cv2.addWeighted(display, 0.6, combined_mask, 0.4, 0, display)

        if pointer and self.region:
            scale_x = preview_w / self.region['width']
            scale_y = preview_h / self.region['height']
            px = int(pointer[0] * scale_x)
            py = int(pointer[1] * scale_y)
            color = (0, 255, 255) if hit else (128, 128, 128)
            cv2.circle(display, (px, py), 6, color, -1)
            if triggered:
                cv2.circle(display, (px, py), 12, (0, 255, 0), 3)

        with self._lock:
            speed_label = self._detected_mode_label
            speed = self._measured_speed

        status = f"{speed_label} {'HIT!' if hit else '---'} {'[TRIG]' if triggered else ''}"
        color = (0, 255, 0) if triggered else (200, 200, 200)
        cv2.putText(display, status, (5, 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, color, 1)

        cv2.putText(display, f"{speed:.0f}d/s", (155, 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.4, (150, 150, 150), 1)

        return cv2.cvtColor(display, cv2.COLOR_BGR2RGB)

    @property
    def latest_preview(self):
        with self._preview_lock:
            return self._latest_preview

    @property
    def latency_log(self):
        with self._lock:
            return list(self._latency_log)

    @property
    def detected_mode_label(self) -> str:
        with self._lock:
            return self._detected_mode_label

    @property
    def measured_speed(self) -> float:
        with self._lock:
            return self._measured_speed

    def get_stats(self) -> dict:
        with self._lock:
            if self._latency_count == 0:
                return {}
            avg_latency = self._latency_sum / self._latency_count
            max_latency = self._latency_max
            hit_log = list(self._hit_log)
            trigger_count = self._trigger_count
            frame_count = self._frame_count
            speed = self._measured_speed
            mode_label = self._detected_mode_label
            latency_log = list(self._latency_log)

        p99_latency = np.percentile(latency_log, 99) if latency_log else 0.0

        return {
            "avg_latency": f"{avg_latency:.2f}ms",
            "p99_latency": f"{p99_latency:.2f}ms",
            "max_latency": f"{max_latency:.2f}ms",
            "trigger_count": trigger_count,
            "frame_count": frame_count,
            "hit_rate": f"{np.mean(hit_log) * 100:.1f}%" if hit_log else "0%",
            "auto_mode": mode_label,
            "speed": f"{speed:.0f}°/s",
        }

    def start(self, preview: bool = True):
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
        if self._obs_capture is not None:
            self._obs_capture.release()
            self._obs_capture = None

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        return self.paused
