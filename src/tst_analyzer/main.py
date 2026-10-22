"""命令行入口：解析参数、驱动交互配置、逐帧分析并导出结果。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import cv2

from . import __version__
from .analyzer import MouseAnalyzer, print_summary, save_results
from .config import DEFAULT_FILENAME, DEFAULT_VIDEO_PATH, RESULT_WINDOW_NAME
from .gui import UserCancelled, safe_fps
from .interactive import interactive_setup


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tst-analyzer",
        description="多小鼠尾悬挂实验（TST）视频分析：按 ROI 统计挣扎 / 静止时间。",
        epilog="示例: tst-analyzer video.mp4 -o results.csv",
    )
    parser.add_argument(
        "video",
        nargs="?",
        help=f"视频文件路径（省略时使用 {DEFAULT_VIDEO_PATH}）",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_FILENAME,
        help=f"结果 CSV 输出路径（默认 {DEFAULT_FILENAME}）",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _open_writer(filename: str, fps: float, size):
    """创建视频写入器，MP4V 不可用时退回 XVID。"""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(filename, fourcc, fps, size)
    if writer.isOpened():
        print(f"已创建视频写入器: {filename}")
        return writer, filename

    writer.release()
    alt = str(Path(filename).with_suffix(".avi"))
    writer = cv2.VideoWriter(alt, cv2.VideoWriter_fourcc(*"XVID"), fps, size)
    if writer.isOpened():
        print(f"警告: MP4V 编码不可用，已改用 XVID 保存到 {alt}")
        return writer, alt

    writer.release()
    print("错误: 无法初始化视频写入器，将不保存输出视频。")
    return None, filename


def run_analysis(
    cap,
    analyzers: List[MouseAnalyzer],
    video_config: dict,
    frame_skip: int,
) -> None:
    """逐帧分析：每 ``frame_skip`` 帧做一次判定，每帧都绘制叠加层。"""
    fps = safe_fps(cap)
    for analyzer in analyzers:
        analyzer.frame_rate = fps

    print(f"\n视频帧率 (FPS): {fps:.2f}")
    print(f"分析将以每 {frame_skip} 帧 1 次的密度进行。")

    writer = None
    if video_config["save"]:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writer, video_config["filename"] = _open_writer(
            video_config["filename"], fps, (width, height)
        )

    start_frame_save = int(video_config["start_s"] * fps)
    end_frame_save = int(video_config["end_s"] * fps)

    cv2.namedWindow(RESULT_WINDOW_NAME, cv2.WINDOW_NORMAL)

    frame_count = 0
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break

        current_time_s = frame_count / fps if fps > 0 else 0.0

        # 运动检测只在抽样帧上做
        if frame_count % frame_skip == 0:
            for analyzer in analyzers:
                analyzer.process_frame(frame, current_time_s)

        # 叠加层每帧绘制，方便肉眼核对
        for analyzer in analyzers:
            color = (255, 0, 0)  # 蓝：不在分析时间窗内
            status_text = f"{analyzer.name}: Inactive"
            if analyzer.is_active:
                if analyzer.current_state_is_moving:
                    color = (0, 255, 0)  # 绿：挣扎
                    status_text = f"{analyzer.name}: Struggling"
                else:
                    color = (0, 0, 255)  # 红：静止
                    status_text = f"{analyzer.name}: Stationary"

            x, y, w, h = analyzer.roi
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(
                frame,
                status_text,
                (x, max(y - 10, 12)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
                cv2.LINE_AA,
            )

        cv2.putText(
            frame,
            f"Time: {current_time_s:.2f} s | Freq: 1/{frame_skip} | FPS: {fps:.1f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.imshow(RESULT_WINDOW_NAME, frame)

        if writer is not None:
            if start_frame_save <= frame_count < end_frame_save:
                writer.write(frame)
            elif frame_count >= end_frame_save:
                writer.release()
                writer = None
                print(f"输出视频保存完成: {video_config['filename']}")

        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("用户中止分析，已处理的部分仍会保存。")
            break

        frame_count += 1

    cv2.destroyAllWindows()
    if writer is not None:
        writer.release()
        print(f"输出视频保存完成: {video_config['filename']}")


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    video_path = args.video or DEFAULT_VIDEO_PATH
    if not args.video:
        print(f"警告: 未指定视频路径，尝试使用默认路径: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"错误: 无法打开视频文件: {video_path}")
        return 1

    try:
        analyzers, video_config, frame_skip = interactive_setup(cap)
        if not analyzers:
            print("没有有效的小鼠分析任务，程序退出。")
            return 0

        run_analysis(cap, analyzers, video_config, frame_skip)
    except UserCancelled as exc:
        print(f"{exc}程序退出。")
        return 130
    except KeyboardInterrupt:
        print("\n已中断。")
        return 130
    except Exception as exc:  # noqa: BLE001 - 顶层兜底，给出可读错误
        print(f"程序运行失败: {exc}")
        return 1
    finally:
        cap.release()
        cv2.destroyAllWindows()

    try:
        saved = save_results(analyzers, args.output)
        print(f"\n分析结果已成功保存到文件: {saved}")
    except OSError as exc:
        print(f"\n保存结果时发生错误: {exc}")
        return 1

    print_summary(analyzers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
