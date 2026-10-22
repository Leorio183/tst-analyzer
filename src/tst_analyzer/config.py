"""全局默认参数。

这些数值是尾悬挂实验（TST）判定的默认值，交互式设置时用户可逐项覆盖。
"""

# 低灵敏度：平均像素差阈值。低于此值视为"完全静止"。
DEFAULT_SENSITIVITY = 5.0

# 高灵敏度：平均像素差阈值。超过此值才可能启动"挣扎"连贯计数。
DEFAULT_HIGH_SENSITIVITY = 10.0

# 运动连贯性参数（用于过滤惯性晃动）
DEFAULT_MIN_MOVE_FRAMES = 5
DEFAULT_MAX_QUIET_FRAMES = 30

# 未指定视频路径时的兜底文件
DEFAULT_VIDEO_PATH = "video.mp4"

# 结果 CSV 的默认文件名
DEFAULT_FILENAME = "multi_mouse_tst_results.csv"

# 视频无法读取帧率时假定的帧率
DEFAULT_FPS_FALLBACK = 30.0

# 窗口标题
FRAME_SELECTOR_WINDOW = "Video Reference (Press 'Enter' or 'Space' to confirm)"
RESULT_WINDOW_NAME = "Multi-Mouse TST Analysis (Press 'q' to quit)"
