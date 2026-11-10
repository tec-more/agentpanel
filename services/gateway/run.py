"""网关独立服务启动器（本地开发用）。

用法（仓库根目录）：
    python services/gateway/run.py

说明：工程以脚本方式启动：把工程目录与仓库根加入 sys.path 后加载
`app.main`，使本地（仓库根）与容器（WORKDIR=/app，共享包以 wheel 安装）
两种目录布局共用同一入口。
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
