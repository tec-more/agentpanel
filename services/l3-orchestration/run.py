"""L3 编排独立服务启动器（本地开发用）。

用法（仓库根目录）：
    python services/l3-orchestration/run.py

说明：目录名含连字符，无法 `python -m services.l3-orchestration.app.main`，
因此由本脚本把工程目录与仓库根加入 sys.path 后再加载 `app.main`。
容器内使用 `uvicorn app.main:app`（WORKDIR=/app，共享包以 wheel 安装）。
"""
import pathlib
import sys

PROJECT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parents[1]
for entry in (str(PROJECT_DIR), str(REPO_ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from app.main import main  # noqa: E402

if __name__ == "__main__":
    main()
