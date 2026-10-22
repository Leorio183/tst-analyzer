"""终端交互：采集连贯性阈值、灵敏度、ROI 与分析时间等配置。

所有提问都带默认值，直接回车即走默认，便于重复实验时快速通过。
"""

from __future__ import annotations

from typing import List, Optional

import cv2

from .analyzer import MouseAnalyzer
from .config import (
    DEFAULT_FILENAME,
    DEFAULT_HIGH_SENSITIVITY,
    DEFAULT_MAX_QUIET_FRAMES,
    DEFAULT_MIN_MOVE_FRAMES,
    DEFAULT_SENSITIVITY,
)
from .gui import safe_fps, select_initial_frame, select_roi, select_time_point


# --------------------------------------------------------------------- 输入助手
def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def ask_int(prompt: str, default: int, minimum: int = 1) -> int:
    """读一个 >= minimum 的整数，空输入返回默认值。"""
    while True:
        raw = input(f"{prompt}（默认 {default}）: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("输入无效，请输入整数。")
            continue
        if value < minimum:
            print(f"数值必须 >= {minimum}。")
            continue
        return value


def ask_float(
    prompt: str,
    default: float,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
    exclusive_min: bool = False,
) -> float:
    """读一个浮点数，空输入返回默认值，可按区间校验。"""
    while True:
        raw = input(f"{prompt}（默认 {_fmt(default)}）: ").strip()
        if not raw:
            return default
        try:
            value = float(raw)
        except ValueError:
            print("输入无效，请输入数字。")
            continue
        if minimum is not None:
            if exclusive_min and value <= minimum:
                print(f"数值必须 > {_fmt(minimum)}。")
                continue
            if not exclusive_min and value < minimum:
                print(f"数值必须 >= {_fmt(minimum)}。")
                continue
        if maximum is not None and value > maximum:
            print(f"数值必须 <= {_fmt(maximum)}。")
            continue
        return value


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{hint}]: ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("请输入 y 或 n。")


def _draw_existing_rois(frame, analyzers: List[MouseAnalyzer]):
    """在基准帧上把已画好的 ROI 标成黄色，方便避免重叠。"""
    canvas = frame.copy()
    for analyzer in analyzers:
        x, y, w, h = analyzer.roi
        cv2.rectangle(canvas, (x, y), (x + w, y + h), (0, 255, 255), 2)
        cv2.putText(
            canvas,
            analyzer.name,
            (x, max(y - 5, 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return canvas


# --------------------------------------------------------------------- 主流程
def interactive_setup(cap):
    """引导用户完成全部配置，返回 ``(analyzers, video_config, frame_skip)``。"""
    print("\n--- 交互式分析设置 ---")

    fps = safe_fps(cap)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    total_duration_s = total_frames / fps if fps > 0 else 0.0

    # 1. 运动连贯性参数
    print("\n--- 运动连贯性参数设置（用于过滤轻微晃动 / 噪声）---")
    min_movement_frames = ask_int(
        "1. 最小连续运动帧数：必须连续【大幅度】运动 N 帧才算“挣扎”",
        DEFAULT_MIN_MOVE_FRAMES,
    )
    max_stationary_frames = ask_int(
        "2. 最大连续静止帧数：必须连续【完全静止】N 帧才算“绝望/静止”",
        DEFAULT_MAX_QUIET_FRAMES,
    )
    print(f"已设置连贯性阈值：大幅度运动需持续 {min_movement_frames} 帧，完全静止需持续 {max_stationary_frames} 帧。")

    # 2. 分析密度
    frame_skip = ask_int("3. 分析密度：每 N 帧分析 1 帧（N=1 即分析所有帧）", 1)

    # 3. 小鼠数量
    num_mice = ask_int("\n4. 要分析的小鼠数量", 1)

    # 4. ROI 基准帧
    try:
        base_frame, base_frame_pos = select_initial_frame(cap)
    except Exception as exc:  # noqa: BLE001 - 统一转成可读错误
        raise RuntimeError(f"基准帧选择失败: {exc}") from exc
    del base_frame  # 只需位置，后续按位置重新读取

    # 5. 全局灵敏度（个体可覆盖）
    print("\n--- 灵敏度设置 ---")
    default_sensitivity = ask_float(
        "全局低灵敏度（判断完全静止的阈值）", DEFAULT_SENSITIVITY, minimum=0.0
    )
    default_high_sensitivity = ask_float(
        "全局高灵敏度（判断主动挣扎的阈值）", DEFAULT_HIGH_SENSITIVITY, minimum=0.0
    )
    if default_high_sensitivity <= default_sensitivity:
        default_high_sensitivity = default_sensitivity + 1.0
        print(f"警告：高灵敏度必须严格大于低灵敏度，已自动设为 {default_high_sensitivity:g}。")

    # 6. 逐只小鼠配置
    analyzers: List[MouseAnalyzer] = []
    for index in range(num_mice):
        while True:
            mouse_name = input(f"\n请输入第 {index + 1} 只小鼠的名称（例如 MouseA）: ").strip()
            if mouse_name:
                break
            print("名称不能为空。")

        cap.set(cv2.CAP_PROP_POS_FRAMES, base_frame_pos)
        ok, current_frame = cap.read()
        if not ok:
            raise RuntimeError("无法读取 ROI 绘制基准帧。")

        rect = select_roi(
            f"Select ROI for {mouse_name}",
            _draw_existing_rois(current_frame, analyzers),
            mouse_name,
        )
        if rect is None:
            print(f"警告：{mouse_name} 的 ROI 选择无效，已跳过该小鼠。")
            continue

        # 6.1 分析时间：GUI 粗选 + 终端微调
        print(f"\n--- 为 {mouse_name} 设置分析时间（视频总长 {total_duration_s:.2f}s）---")
        start_gui = select_time_point(cap, "分析开始时间", default_pos=0)
        print(f"GUI 选定开始时间为 {start_gui:.2f} 秒。")
        start_s = ask_float(
            f"请确认或微调 {mouse_name} 的分析开始时间（秒）",
            start_gui,
            minimum=0.0,
            maximum=total_duration_s,
        )

        end_gui = select_time_point(cap, "分析结束时间", default_pos=int(start_s * fps))
        print(f"GUI 选定结束时间为 {end_gui:.2f} 秒。")
        end_s = ask_float(
            f"请确认或微调 {mouse_name} 的分析结束时间（秒）",
            end_gui,
            minimum=start_s,
            maximum=total_duration_s,
            exclusive_min=True,
        )
        print(f"已设置 {mouse_name}: 分析范围 {start_s:.2f}s 到 {end_s:.2f}s")

        # 6.2 个体灵敏度
        sensitivity = ask_float(
            f"{mouse_name} 的低灵敏度", default_sensitivity, minimum=0.0
        )
        high_sensitivity = ask_float(
            f"{mouse_name} 的高灵敏度", default_high_sensitivity, minimum=0.0
        )
        if high_sensitivity <= sensitivity:
            high_sensitivity = sensitivity + 1.0
            print(f"警告：高灵敏度必须大于低灵敏度，已自动设为 {high_sensitivity:g}。")

        analyzers.append(
            MouseAnalyzer(
                mouse_name,
                rect,
                start_s,
                end_s,
                sensitivity,
                high_sensitivity,
                min_movement_frames,
                max_stationary_frames,
                frame_skip=frame_skip,
            )
        )

    if not analyzers:
        print("没有有效的小鼠分析任务。")
        return analyzers, _no_video(), frame_skip

    # 7. 输出视频（可选）
    print("\n--- 输出视频保存设置 ---")
    video_config = _configure_video_output(cap, total_duration_s, fps)

    # 8. 回到视频开头，准备正式分析
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    return analyzers, video_config, frame_skip


def _no_video() -> dict:
    return {"save": False, "filename": None, "start_s": 0.0, "end_s": 0.0}


def _configure_video_output(cap, total_duration_s: float, fps: float) -> dict:
    if not ask_yes_no("是否保存分析过程中带标记的视频？", default=False):
        return _no_video()

    while True:
        filename = input(f"请输入保存视频的文件名（例如 output.mp4，默认 {DEFAULT_FILENAME.replace('.csv', '.mp4')}）: ").strip()
        if not filename:
            filename = DEFAULT_FILENAME.replace(".csv", ".mp4")
        if filename:
            break
        print("文件名不能为空。")

    start_gui = select_time_point(cap, "输出视频剪辑开始时间", default_pos=0)
    print(f"GUI 选定剪辑开始时间为 {start_gui:.2f} 秒。")
    start_s = ask_float(
        "请确认或微调输出视频开始时间（秒）",
        start_gui,
        minimum=0.0,
        maximum=total_duration_s,
    )

    end_gui = select_time_point(cap, "输出视频剪辑结束时间", default_pos=int(start_s * fps))
    print(f"GUI 选定剪辑结束时间为 {end_gui:.2f} 秒。")
    end_s = ask_float(
        "请确认或微调输出视频结束时间（秒）",
        end_gui,
        minimum=start_s,
        maximum=total_duration_s,
        exclusive_min=True,
    )

    print(f"输出视频将保存为 {filename}，范围 {start_s:.2f}s 到 {end_s:.2f}s。")
    return {"save": True, "filename": filename, "start_s": start_s, "end_s": end_s}
