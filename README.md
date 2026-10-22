# tst-analyzer

多小鼠尾悬挂实验（Tail Suspension Test, TST）视频分析工具：给每个 ROI 框一只小鼠，自动统计它在分析时间窗内的**挣扎时间**与**静止（绝望）时间**，输出 CSV 统计表，可选导出一份带状态标记的视频。

- 双灵敏度阈值 + 运动连贯性过滤，用来排除"身体随绳子惯性轻晃"造成的假挣扎
- 纯 OpenCV 帧间差分，不需要训练模型、不需要 GPU
- 一台机器上可以一次分析同一视频里的多只小鼠（各自的 ROI 和时间窗）

---

## 安装

### 方式一：conda（推荐，GUI 依赖一次装好）

```bash
git clone https://github.com/Leorio183/tst-analyzer.git
cd tst-analyzer
conda env create -f environment.yml
conda activate tst-analyzer
```

### 方式二：pip

```bash
git clone https://github.com/Leorio183/tst-analyzer.git
cd tst-analyzer
pip install -e .
```

> 需要带 GUI 的 OpenCV（`opencv-python`），因为要弹窗选帧、画 ROI。`opencv-python-headless` 只能在 CI 里跑测试，不能交互使用。

---

## 一条能复制的用法

```bash
tst-analyzer /path/to/video.mp4 -o results.csv
```

或者用模块方式运行：

```bash
python -m tst_analyzer /path/to/video.mp4 -o results.csv
```

程序会依次弹出窗口让你确认，然后开始分析。全程终端也会提示每一步在问什么。

### 命令行参数

| 参数 | 说明 |
| --- | --- |
| `video` | 视频文件路径。省略时尝试当前目录下的 `video.mp4` |
| `-o, --output` | 结果 CSV 路径，默认 `multi_mouse_tst_results.csv` |
| `--version` | 显示版本号 |
| `-h, --help` | 显示帮助 |

---

## 交互流程

```
1. 最小连续运动帧数        连续 N 帧"大幅度"运动才算挣扎（默认 5）
2. 最大连续静止帧数        连续 N 帧"完全静止"才算静止/绝望（默认 30）
3. 分析密度                每 N 帧分析 1 帧，跳帧加速（默认 1，即全帧）
4. 小鼠数量
5. ROI 基准帧              拖动滑动条选一帧，Enter 确认
6. 全局低/高灵敏度         判断"完全静止"与"主动挣扎"的像素差阈值
7. 逐只小鼠：名称 → 框选 ROI → 选开始时间 → 选结束时间 → 个体灵敏度
8. 是否保存标记视频（可选，可指定剪辑区间）
```

窗口快捷键：`Enter` / `Space` 确认，`q` 取消并退出。

### 参数怎么调

| 参数 | 含义 | 调大的效果 |
| --- | --- | --- |
| 低灵敏度 | 平均像素差 <= 该值视为完全静止 | 更难判为静止，静止时间变少 |
| 高灵敏度 | 平均像素差 > 该值才可能启动挣扎计数 | 更难判为挣扎，能滤掉更多轻晃 |
| 最小连续运动帧数 | 挣扎需要持续的帧数 | 更严格，短暂抖动被忽略 |
| 最大连续静止帧数 | 静止需要持续的帧数 | 更难判定"放弃挣扎"，静止时间变少 |
| 分析密度 N | 每 N 帧取 1 帧判定 | 更快，但时间分辨率变粗 |

建议先用默认值跑一遍，看输出视频里的 ROI 颜色（绿=挣扎 / 红=静止 / 蓝=不在分析窗口），再针对录像的噪声水平微调两个阈值。

> 灵敏度是**像素灰度平均绝对差**，跟摄像头、光照、镜头距离强相关，不能照搬别人的数值。

---

## 输出

CSV 每行一只小鼠，列含义：

| 列 | 含义 |
| --- | --- |
| `Mouse_Name` | 小鼠名称 |
| `Start_Time_s` / `End_Time_s` | 分析时间窗（秒） |
| `Total_Analysis_Time_s` | 实际统计到的总时长（秒） |
| `Movement_Time_s` / `Stationary_Time_s` | 挣扎 / 静止时长（秒） |
| `Movement_Proportion_Percent` | 挣扎时长占比（%） |
| `Movement_Frames` / `Stationary_Frames` | 计数帧数（已分析帧数，非原始帧数） |
| `Low_Sensitivity_Threshold` / `High_Sensitivity_Threshold` | 本次使用的双阈值 |
| `Min_Movement_Frames_Threshold` / `Max_Stationary_Frames_Threshold` | 本次使用的连贯性参数 |
| `ROI_X` / `ROI_Y` / `ROI_W` / `ROI_H` | ROI 位置与尺寸（像素） |

时间按 `帧数 × 分析密度 / FPS` 折算，跳帧分析时也是真实秒数。

---

## 工作原理

1. 对每个 ROI，取相邻两帧的灰度图做绝对差分，取平均得到 `change`；
2. `change > 高灵敏度` 且连续 `最小连续运动帧数` 帧 → 状态切到「挣扎」；
3. 进入「挣扎」后，`change <= 低灵敏度` 且连续 `最大连续静止帧数` 帧 → 状态切回「静止」；
4. 每一帧的判定结果累加到对应计数器，最后按 FPS 换算成秒。

两个阈值的作用：高阈值保证只有"真的在动"才启动挣扎计时，低阈值保证只有"彻底不动"才计入静止，中间那段（惯性轻晃）两边都不算，避免把晃动误记成挣扎。

---

## 常见问题

**弹不出窗口 / 报 `cv2.error: ... The function is not implemented`**
装的是 headless 版 OpenCV。换成 `pip install opencv-python`，或按 `environment.yml` 用 conda 安装。

**提示 MP4V 编码不可用，改存了 .avi**
本机 OpenCV 没编进 H.264/MP4 编码器。程序会自动退回 XVID，不影响分析，需要 MP4 可以用 ffmpeg 转。

**分析到一半按 q 会丢结果吗**
不会，已处理的部分照常写 CSV，只是后面没分析。

**多机位/多人实验怎么保证可比性**
固定摄像头高度与光照，用同一组阈值；阈值一旦确定就写进实验记录，别每批数据都改。

---

## 开发

```bash
pip install -e . --no-deps
pip install numpy opencv-python-headless pytest
pytest test -q
```

- `.github/workflows/ci.yml`：推到 GitHub 后自动在 Ubuntu/Windows × Python 3.9/3.11/3.12 上安装并跑 pytest
- `.cnb.yml`：推到 CNB 后跑同一组命令

代码结构：

```
src/tst_analyzer/
├── config.py       # 默认参数
├── analyzer.py     # 判定状态机 + CSV 导出 + 终端摘要
├── gui.py          # 滑动条选帧、选时间点、框选 ROI
├── interactive.py  # 终端问询流程
└── main.py         # argparse 入口 + 逐帧分析循环
```

---

## 许可

MIT，见 [LICENSE](LICENSE)。正式对外发布前，可按单位要求替换为相应授权文本（同时更新 `setup.py` 里的 classifier）。
