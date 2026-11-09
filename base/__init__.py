"""L2 业务后端包。

注意：这里**不再**做 `start`/`core`/`cli` 的 eager import。L3 入口（`services/gateway/run.py`、
`services/orchestration/run.py`）只导入自身依赖链，避免把 L2 的应用装配（`base.start`）
带进独立进程。L2 入口通过 `base.app_wrapper` 显式导入 `base.start`。
"""
