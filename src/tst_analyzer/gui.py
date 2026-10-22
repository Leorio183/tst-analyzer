"""OpenCV 交互窗口：滑动条选帧、选时间点、绘制 ROI。

只有需要人工确认的环节才走 GUI，其余交互都在终端完成。
"""

from __future__ import annotations

import time

import cv2

from .config import DEFAULT_FPS_FALLBACK, FRAME_SELECTOR_WINDOW


class UserCancelled(Exception):
    """用户在 GUI 中按 q 主动取消。"""


def safe_fps(cap) -> float:
    """读取帧率，读不到（0 / NaN）时回退到默认值。"""
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
    except (TypeError, ValueError):
        fps = 0.0
    return fps if fps > 0 else DEFAULT_FPS_FALLBACK


class FrameSlider:
    """带滑动条的参考帧预览窗口。"""

    def __init__(self, cap) -> None:
        self.cap = cap
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = safe_fps(cap)
        self.pos = 0
        self.frame = None
        self.window = FRAME_SELECTOR_WINDOW

    # ------------------------------------------------------------------ 内部
    def _seek(self, pos: int) -> None:
        pos = max(0, min(int(pos), max(self.total_frames - 1, 0)))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ok, frame = self.cap.read()
        if ok:
            self.frame = frame.copy()
            time_s = pos / self.fps if self.fps > 0 else 0.0
            cv2.putText(
                self.frame,
                f"Frame: {pos} / Time: {time_s:.2f}s",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )
            cv2.imshow(self.window, self.frame)
        self.pos = pos

    def _on_trackbar(self, pos: int) -> None:
        self._seek(pos)

    def _window_closed(self) -> bool:
        try:
            return cv2.getWindowProperty(self.window, cv2.WND_PROP_VISIBLE) < 1
        except cv2.error:
            return True

    # ------------------------------------------------------------------ 对外
    def open(self, initial: int = 0) -> bool:
        """打开窗口并定位到初始帧；视频过短时返回 False。"""
        if self.total_frames <= 1:
            return False

        initial = max(0, min(int(initial), self.total_frames - 1))
        cv2.namedWindow(self.window, cv2.WINDOW_NORMAL)
        cv2.createTrackbar("Frame Position", self.window, 0, self.total_frames - 1, self._on_trackbar)
        cv2.setTrackbarPos("Frame Position", self.window, initial)
        self._seek(initial)
        cv2.waitKey(1)
        return True

    def wait_confirm(self) -> None:
        """阻塞等待 Enter / Space 确认；q 取消；直接关窗口视为确认。"""
        while True:
            key = cv2.waitKey(0) & 0xFF
            if key in (13, 32):  # Enter / Space
                cv2.destroyAllWindows()
                return
            if key == ord("q"):
                cv2.destroyAllWindows()
                raise UserCancelled("用户取消操作。")
            if self._window_closed():
                cv2.destroyAllWindows()
                return
            time.sleep(0.01)

    def frame_at(self, pos: int):
        """重新读取指定帧（避免依赖上一帧的缓冲状态）。"""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(pos))
        ok, frame = self.cap.read()
        return frame if ok else None


def select_time_point(cap, prompt: str, default_pos: int = 0) -> float:
    """让用户用滑动条选一个时间点，返回秒数。"""
    print(f"\n--- {prompt}（GUI 选择）---")
    fps = safe_fps(cap)

    slider = FrameSlider(cap)
    if not slider.open(default_pos):
        print("视频太短，无法选择时间点，使用默认位置。")
        return default_pos / fps

    print(f"拖动滑动条查看视频，确定合适的「{prompt}」后按 Enter 或 Space 确认（按 q 取消）。")
    slider.wait_confirm()
    return slider.pos / fps


def select_initial_frame(cap):
    """让用户选一帧作为绘制 ROI 的基准帧，返回 ``(frame, frame_pos)``。"""
    print("\n--- ROI 基准帧选择 ---")

    slider = FrameSlider(cap)
    if not slider.open(0):
        raise RuntimeError("视频太短，无法选择基准帧。")

    print("拖动滑动条查看视频，确定合适的基准帧后按 Enter 或 Space 确认（按 q 取消）。")
    slider.wait_confirm()

    pos = slider.pos
    frame = slider.frame_at(pos)
    if frame is None:
        raise RuntimeError("无法读取选定的基准帧。")

    print(f"ROI 基准帧已选定在 {pos} 帧。")
    return frame, pos


def select_roi(window_name: str, image, mouse_name: str):
    """弹出 ROI 选择窗口，返回 ``(x, y, w, h)`` 或 None（无效选择）。"""
    print(f"请为 {mouse_name} 拖动鼠标框选 ROI，然后按 Enter 或 Space 确认。")
    labeled = image.copy()
    cv2.putText(
        labeled,
        f"Selecting ROI for: {mouse_name}",
        (10, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 255),
        2,
    )

    rect = cv2.selectROI(window_name, labeled, False)
    try:
        cv2.destroyWindow(window_name)
    except cv2.error:
        pass

    if rect[2] <= 0 or rect[3] <= 0:
        return None
    return tuple(int(v) for v in rect)
