"""核心判定逻辑：帧间差分 + 双灵敏度阈值 + 运动连贯性过滤，以及结果导出。

每只小鼠对应一个 :class:`MouseAnalyzer`，它只关心自己 ROI 内的像素变化：

* 相邻两帧 ROI 灰度图的平均绝对差分 ``change`` 作为"运动幅度"。
* ``change > high_sensitivity`` 且连续 ``min_move_frames`` 帧 -> 判定为"挣扎"。
* 判定为挣扎后，``change <= sensitivity`` 且连续 ``max_quiet_frames`` 帧 -> 判定为"静止"。

双重阈值加连贯性要求，是为了把"身体随绳子惯性轻晃"和"主动挣扎"区分开。
"""

from __future__ import annotations

import csv
from typing import Iterable, List, Sequence

import cv2
import numpy as np

CSV_HEADER = [
    "Mouse_Name",
    "Start_Time_s",
    "End_Time_s",
    "Total_Analysis_Time_s",
    "Movement_Time_s",
    "Stationary_Time_s",
    "Movement_Proportion_Percent",
    "Movement_Frames",
    "Stationary_Frames",
    "Low_Sensitivity_Threshold",
    "High_Sensitivity_Threshold",
    "Min_Movement_Frames_Threshold",
    "Max_Stationary_Frames_Threshold",
    "ROI_X",
    "ROI_Y",
    "ROI_W",
    "ROI_H",
]


class MouseAnalyzer:
    """单只小鼠的状态机与计数。"""

    def __init__(
        self,
        name: str,
        roi: Sequence[int],
        start_s: float,
        end_s: float,
        sensitivity: float,
        high_sensitivity: float,
        min_move_frames: int,
        max_quiet_frames: int,
        frame_skip: int = 1,
    ) -> None:
        self.name = name
        self.roi = tuple(int(v) for v in roi)  # (x, y, w, h)
        self.start_s = start_s
        self.end_s = end_s
        self.sensitivity = sensitivity          # 低阈值：判断是否完全静止
        self.high_sensitivity = high_sensitivity  # 高阈值：启动挣扎计数
        self.frame_rate = 0.0                   # 视频帧率，分析前由主流程注入
        self.frame_skip = max(1, int(frame_skip))  # 每 N 帧分析 1 帧

        # 连贯性过滤参数
        self.min_movement_frames = min_move_frames
        self.max_stationary_frames = max_quiet_frames

        # 状态跟踪
        self.move_count = 0   # 确认的运动帧计数（已分析帧数，非原始帧数）
        self.quiet_count = 0  # 确认的静止帧计数
        self.instantaneous_movement_count = 0  # 连续大幅度帧计数
        self.instantaneous_quiet_count = 0     # 连续完全静止帧计数

        self.frame_prev_roi = None
        self.is_active = False
        self.current_state_is_moving = False

    # ------------------------------------------------------------------ 分析
    def process_frame(self, frame_curr: np.ndarray, current_time_s: float):
        """处理一帧，返回 ``(当前是否判定为运动, 平均像素差)``。"""
        # 1. 时间窗检查
        if current_time_s < self.start_s or current_time_s >= self.end_s:
            self.is_active = False
            self.current_state_is_moving = False
            return False, 0.0

        self.is_active = True

        # 2. 裁剪 ROI
        x, y, w, h = self.roi
        y_end = min(y + h, frame_curr.shape[0])
        x_end = min(x + w, frame_curr.shape[1])
        roi_curr_color = frame_curr[y:y_end, x:x_end]

        if roi_curr_color.size == 0 or roi_curr_color.shape[0] != h or roi_curr_color.shape[1] != w:
            return self.current_state_is_moving, 0.0

        roi_curr_gray = cv2.cvtColor(roi_curr_color, cv2.COLOR_BGR2GRAY)

        # 3. 帧间差分
        change = 0.0
        if self.frame_prev_roi is not None and roi_curr_gray.shape == self.frame_prev_roi.shape:
            grey_diff = cv2.absdiff(self.frame_prev_roi, roi_curr_gray)
            change = float(np.average(grey_diff))

        is_any_movement = change > self.sensitivity        # 低阈值：有任何运动
        is_major_movement = change > self.high_sensitivity  # 高阈值：大幅挣扎

        # 4. 连贯性过滤与状态切换
        if not self.current_state_is_moving:
            if is_major_movement:
                self.instantaneous_movement_count += 1
                if self.instantaneous_movement_count >= self.min_movement_frames:
                    self.current_state_is_moving = True
                    self.instantaneous_movement_count = 0
            else:
                self.instantaneous_movement_count = 0

        if self.current_state_is_moving:
            if not is_any_movement:
                self.instantaneous_quiet_count += 1
                if self.instantaneous_quiet_count >= self.max_stationary_frames:
                    self.current_state_is_moving = False
                    self.instantaneous_quiet_count = 0
            else:
                self.instantaneous_quiet_count = 0

        # 5. 只对确认后的状态计数
        if self.current_state_is_moving:
            self.move_count += 1
        else:
            self.quiet_count += 1

        # 6. 缓存上一帧
        if roi_curr_gray.size > 0:
            self.frame_prev_roi = roi_curr_gray.copy()

        return self.current_state_is_moving, change

    # ------------------------------------------------------------------ 结果
    @property
    def analyzed_frames(self) -> int:
        return self.move_count + self.quiet_count

    def get_results(self) -> dict:
        """汇总结果。时间按 ``frame_skip`` 折算回真实的视频时间。"""
        analyzed = self.analyzed_frames
        fps = self.frame_rate
        step = self.frame_skip

        if analyzed == 0 or fps <= 0:
            total_s = move_s = quiet_s = 0.0
        else:
            total_s = analyzed * step / fps
            move_s = self.move_count * step / fps
            quiet_s = self.quiet_count * step / fps

        proportion = (self.move_count / analyzed * 100.0) if analyzed else 0.0

        return {
            "name": self.name,
            "roi": self.roi,
            "total_time_s": total_s,
            "move_s": move_s,
            "quiet_s": quiet_s,
            "proportion": proportion,
            "move_count": self.move_count,
            "quiet_count": self.quiet_count,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "sensitivity": self.sensitivity,
            "high_sensitivity": self.high_sensitivity,
            "min_move_frames": self.min_movement_frames,
            "max_quiet_frames": self.max_stationary_frames,
            "frame_skip": self.frame_skip,
        }

    def to_csv_row(self) -> List[str]:
        r = self.get_results()
        return [
            r["name"],
            f"{r['start_s']:.2f}",
            f"{r['end_s']:.2f}",
            f"{r['total_time_s']:.2f}",
            f"{r['move_s']:.2f}",
            f"{r['quiet_s']:.2f}",
            f"{r['proportion']:.2f}",
            str(r["move_count"]),
            str(r["quiet_count"]),
            f"{r['sensitivity']:.2f}",
            f"{r['high_sensitivity']:.2f}",
            str(r["min_move_frames"]),
            str(r["max_quiet_frames"]),
            *(str(v) for v in r["roi"]),
        ]


def save_results(analyzers: Iterable[MouseAnalyzer], filename: str) -> str:
    """把每只小鼠的结果写入一份 CSV，返回文件路径。"""
    with open(filename, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADER)
        for analyzer in analyzers:
            writer.writerow(analyzer.to_csv_row())
    return filename


def print_summary(analyzers: Iterable[MouseAnalyzer]) -> None:
    """在终端打印结果摘要。"""
    line = "=" * 80
    print("\n" + line)
    print("                      尾悬挂实验 (TST) 分析结果汇总")
    print(line)

    for analyzer in analyzers:
        r = analyzer.get_results()
        print(f"\n--- 小鼠 ID: {r['name']} ---")
        print(f"分析时间范围: {r['start_s']:.2f}s - {r['end_s']:.2f}s (共 {r['total_time_s']:.2f} 秒)")
        print(f"低灵敏度 (判断静止): <= {r['sensitivity']:.2f}")
        print(f"高灵敏度 (判断挣扎): > {r['high_sensitivity']:.2f}")
        print(f"运动连贯性要求: 挣扎需连续 {r['min_move_frames']} 帧 | 静止需连续 {r['max_quiet_frames']} 帧")
        print("-" * 30)
        print(f"运动/挣扎时间: {r['move_s']:.2f} 秒 ({r['move_count']} 帧)")
        print(f"静止/绝望时间: {r['quiet_s']:.2f} 秒 ({r['quiet_count']} 帧)")
        print(f"运动占总分析时长比例: {r['proportion']:.2f} %")
        print("-" * 30)

    print(line)
