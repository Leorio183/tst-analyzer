"""setuptools 打包配置：包名、版本与命令行入口。"""

import re
from pathlib import Path

from setuptools import find_packages, setup

ROOT = Path(__file__).parent
INIT_FILE = ROOT / "src" / "tst_analyzer" / "__init__.py"

VERSION = re.search(
    r'__version__\s*=\s*"([^"]+)"', INIT_FILE.read_text(encoding="utf-8")
).group(1)

LONG_DESCRIPTION = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""

setup(
    name="tst-analyzer",
    version=VERSION,
    description="多小鼠尾悬挂实验（TST）视频分析：按 ROI 统计挣扎 / 静止时间",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.9",
    install_requires=[
        "numpy>=1.21",
        "opencv-python>=4.5",
    ],
    entry_points={
        "console_scripts": [
            "tst-analyzer = tst_analyzer.main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Scientific/Engineering :: Image Processing",
    ],
    zip_safe=False,
)
