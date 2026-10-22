"""功能测试：用合成帧验证判定状态机与时间换算（不需要 GUI、不需要视频文件）。"""

import numpy as np

from tst_analyzer.analyzer import MouseAnalyzer, save_results


def _frame(value: int = 0, size=(60, 60)) -> np.ndarray:
    """生成一张纯色 BGR 图，充当某个 ROI 的画面。"""
    return np.full((size[0], size[1], 3), value, dtype=np.uint8)


def _analyzer(**kwargs) -> MouseAnalyzer:
    params = dict(
        name="M1",
        roi=(0, 0, 60, 60),
        start_s=0.0,
        end_s=100.0,
        sensitivity=5.0,
        high_sensitivity=10.0,
        min_move_frames=2,
        max_quiet_frames=3,
    )
    params.update(kwargs)
    return MouseAnalyzer(**params)


def test_steady_frames_count_as_stationary():
    analyzer = _analyzer()
    analyzer.frame_rate = 10.0
    for i in range(10):
        analyzer.process_frame(_frame(0), i / 10)

    result = analyzer.get_results()
    assert result["move_count"] == 0
    assert result["quiet_count"] == 10
    assert result["proportion"] == 0.0


def test_alternating_frames_trigger_struggling():
    analyzer = _analyzer(min_move_frames=2)
    analyzer.frame_rate = 10.0
    for i in range(10):
        analyzer.process_frame(_frame(0 if i % 2 == 0 else 100), i / 10)

    # 第 0 帧无参照 -> 静止；第 1、2 帧连续大幅变化后进入挣扎状态
    assert analyzer.current_state_is_moving is True
    assert analyzer.get_results()["move_count"] > 0


def test_time_window_outside_is_ignored():
    analyzer = _analyzer(start_s=1.0, end_s=2.0)
    analyzer.frame_rate = 10.0
    for i in range(30):
        analyzer.process_frame(_frame(0), i / 10)

    result = analyzer.get_results()
    assert result["total_time_s"] == 10 / 10.0  # 只有 1.0s - 2.0s 这 10 帧被统计
    assert result["quiet_count"] == 10


def test_frame_skip_is_converted_back_to_seconds():
    analyzer = _analyzer(frame_skip=2)
    analyzer.frame_rate = 10.0
    for i in range(10):
        analyzer.process_frame(_frame(0), i / 10)

    # 每 2 帧分析 1 帧，10 个分析帧 -> 20 原始帧 -> 2 秒
    assert analyzer.get_results()["total_time_s"] == 2.0


def test_save_results_writes_header_and_row(tmp_path):
    analyzer = _analyzer()
    analyzer.frame_rate = 10.0
    analyzer.process_frame(_frame(0), 0.0)

    target = tmp_path / "results.csv"
    save_results([analyzer], str(target))

    lines = target.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("Mouse_Name,Start_Time_s")
    assert lines[1].startswith("M1,0.00,100.00")
