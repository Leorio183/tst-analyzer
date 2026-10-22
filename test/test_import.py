"""最小冒烟测试：保证包能导入、命令行入口可用。功能测试随后补充。"""

import tst_analyzer
from tst_analyzer.main import build_parser, main


def test_package_imports():
    assert tst_analyzer.__version__


def test_main_is_callable():
    assert callable(main)


def test_parser_accepts_video_path():
    args = build_parser().parse_args(["video.mp4"])
    assert args.video == "video.mp4"
    assert args.output.endswith(".csv")


def test_parser_version_flag_exits():
    try:
        build_parser().parse_args(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
