"""
Region Selector - Full-screen overlay for mouse drag selection.
"""

import cv2
import numpy as np
import mss


class RegionSelector:
    """
    Full-screen overlay allowing mouse drag to define monitoring region.

    Controls:
        - Left Mouse Drag: Draw selection rectangle
        - Enter: Confirm selection
        - R: Reset/clear selection
        - ESC: Cancel
    """

    _BG_COLOR = (20, 20, 20)
    _RECT_COLOR = (0, 255, 0)
    _TEXT_COLOR = (200, 200, 200)
    _CORNER_COLOR = (0, 255, 255)

    def __init__(self):
        self.region = None
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.canvas = None
        self._dirty = True

    def run(self) -> dict:
        screen_h, screen_w = 1080, 1920
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                screen_h = monitor["height"]
                screen_w = monitor["width"]
        except (IndexError, KeyError):
            pass

        self.canvas = np.full((screen_h, screen_w, 3), self._BG_COLOR, dtype=np.uint8)

        cv2.namedWindow("Select Region", cv2.WND_PROP_FULLSCREEN)
        cv2.setWindowProperty("Select Region", cv2.WND_PROP_FULLSCREEN,
                              cv2.WINDOW_FULLSCREEN)
        cv2.setMouseCallback("Select Region", self._mouse_callback)

        while True:
            if self._dirty:
                display = self.canvas.copy()
                self._draw_selection(display, screen_h)
                self._dirty = False
            else:
                display = self.canvas.copy()

            cv2.imshow("Select Region", display)
            key = cv2.waitKey(16) & 0xFF

            if key == 13:
                if self.start_point and self.end_point:
                    x1, y1 = self.start_point
                    x2, y2 = self.end_point
                    self.region = {
                        "left": min(x1, x2),
                        "top": min(y1, y2),
                        "width": abs(x2 - x1),
                        "height": abs(y2 - y1)
                    }
                    break

            elif key == ord('r'):
                self.start_point = None
                self.end_point = None
                self.drawing = False
                self.canvas[:] = self._BG_COLOR
                self._dirty = True

            elif key == 27:
                break

        cv2.destroyAllWindows()
        return self.region

    def _draw_selection(self, display: np.ndarray, screen_h: int):
        if not (self.drawing and self.start_point and self.end_point):
            return

        x1, y1 = self.start_point
        x2, y2 = self.end_point
        cv2.rectangle(display, (x1, y1), (x2, y2), self._RECT_COLOR, 3)

        w, h = abs(x2 - x1), abs(y2 - y1)
        text = f"{w} x {h}"
        cv2.putText(display, text, (min(x1, x2), min(y1, y2) - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, self._RECT_COLOR, 2)

        for pt in [(x1, y1), (x2, y2), (x1, y2), (x2, y1)]:
            cv2.drawMarker(display, pt, self._CORNER_COLOR,
                           cv2.MARKER_CROSS, 15, 2)

        instructions = [
            "Drag to select QTE monitoring region",
            "ENTER = Confirm  |  R = Reset  |  ESC = Cancel"
        ]
        for i, text in enumerate(instructions):
            cv2.putText(display, text, (20, screen_h - 60 + i * 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, self._TEXT_COLOR, 2)

    def _mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_point = (x, y)
            self.end_point = (x, y)
            self._dirty = True

        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            self.end_point = (x, y)
            self._dirty = True

        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            self.end_point = (x, y)
            self._dirty = True
