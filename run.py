#!/usr/bin/env python3
"""
应用启动入口
"""

import sys
import io
import os

# 设置标准输出为 UTF-8 编码（解决 Windows GBK 编码问题）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def _startup_preflight(workers: int) -> None:
    """
    上线硬约束启动自检（H-1 单 worker / H-2 Redis 启用，见 docs/ops/grayscale-monitoring-checklist.md）

    - 生产环境（DEPLOY_ENV=prod/production/docker）违规时：STRICT_STARTUP=true 拒绝启动，false 强警告放行
    - 开发环境：仅警告不阻断
    - 自检直接读 config.conf（不 import base 包，避免启动前副作用）
    """
    import configparser
    import socket
    from pathlib import Path

    conf = configparser.ConfigParser()
    conf_path = Path(__file__).parent / "config.conf"
    if conf_path.exists():
        conf.read(conf_path, encoding="utf-8")

    deploy_env = os.environ.get("DEPLOY_ENV", conf.get("deploy", "env", fallback="dev"))
    strict = os.environ.get(
        "STRICT_STARTUP", conf.get("deploy", "strict_startup", fallback="true")
    ).lower() == "true"
    is_prod = deploy_env.lower() in ("prod", "production", "docker")

    problems = []
    # H-1：生产环境必须单 worker（_controls 进程内注册表约束，cancel/resume 需命中执行进程）
    if workers > 1:
        msg = (f"H-1 硬约束：workers={workers} > 1，cancel/resume 仅命中执行所在进程，"
               f"多 worker 下将随机失效")
        if is_prod:
            problems.append(msg)
        else:
            print(f"⚠️  [{deploy_env}] {msg}", flush=True)
    # H-2：生产环境必须启用 Redis（分布式并发槽 + TTL 兜底，防进程内 _mem_conc 泄漏）
    redis_enabled = conf.getboolean("redis", "enabled", fallback=False)
    if is_prod and not redis_enabled:
        problems.append("H-2 硬约束：生产环境 redis.enabled=false，并发槽将使用无 TTL 的进程内降级，泄漏无兜底")
    # H-2 可达性预检（配置启用时）
    if redis_enabled:
        host = conf.get("redis", "host", fallback="127.0.0.1")
        port = conf.getint("redis", "port", fallback=6379)
        try:
            with socket.create_connection((host, port), timeout=3):
                pass
        except OSError as e:
            msg = f"H-2 Redis 不可达 {host}:{port}（{e}）"
            if is_prod:
                problems.append(msg)
            else:
                print(f"⚠️  [{deploy_env}] {msg}，将降级进程内并发槽", flush=True)

    if problems:
        for p in problems:
            print(f"❌ [preflight] {p}", flush=True)
        if strict:
            print("❌ [preflight] STRICT_STARTUP=true，拒绝启动。修复上述问题，"
                  "或显式设置 STRICT_STARTUP=false 豁免（仅限临时调试）", flush=True)
            sys.exit(2)
        print("⚠️  [preflight] STRICT_STARTUP=false，忽略硬约束违规继续启动（不推荐）", flush=True)


if __name__ == "__main__":
    import uvicorn
    # 从环境变量获取端口，默认9998
    PORT = int(os.environ.get("UVICORN_PORT", "9998"))
    
    # 从环境变量获取配置，或使用默认值
    # Windows 上多 worker 有 socket 继承问题，默认使用单 worker
    import platform
    default_workers = 1 if platform.system() == "Windows" else 2
    WORKERS = int(os.environ.get("UVICORN_WORKERS", str(default_workers)))
    RELOAD = os.environ.get("UVICORN_RELOAD", "false").lower() == "true"  # 生产环境默认关闭reload
    LIMIT_CONCURRENCY = int(os.environ.get("UVICORN_LIMIT_CONCURRENCY", "200"))
    TIMEOUT_KEEP_ALIVE = int(os.environ.get("UVICORN_TIMEOUT_KEEP_ALIVE", "5"))
    
    # 注意：reload 模式下 worker 必须为1，所以如果设置了reload则强制worker=1
    if RELOAD:
        WORKERS = 1

    # 上线硬约束启动自检（H-1/H-2）
    _startup_preflight(WORKERS)

    try:
        print("=" * 70, flush=True)
        print("🚀 AI Panel Admin 服务器启动中...", flush=True)
        print("=" * 70, flush=True)
        print(f"📡 服务地址: http://0.0.0.0:{PORT}", flush=True)
        print(f"📡 本地访问: http://127.0.0.1:{PORT}", flush=True)
        print(f"👷 Worker 数量: {WORKERS}", flush=True)
        print(f"🔄 热重载: {'开启' if RELOAD else '关闭'}", flush=True)
        print(f"📊 并发限制: {LIMIT_CONCURRENCY}", flush=True)
        print(f"⏱️  保持连接超时: {TIMEOUT_KEEP_ALIVE}秒", flush=True)
        print("=" * 70, flush=True)
        
        # 使用 import 字符串格式以支持 reload
        uvicorn.run(
            "base.app_wrapper:app",
            host="0.0.0.0",
            port=PORT,
            workers=WORKERS,
            reload=RELOAD,
            access_log=True,  # 启用访问日志
            log_level="info",  # 设置日志级别
            limit_concurrency=LIMIT_CONCURRENCY,  # 限制并发连接数
            timeout_keep_alive=TIMEOUT_KEEP_ALIVE,  # 保持连接超时
            backlog=128,  # Windows 上需要较小的 backlog 值
        )
    except Exception as e:
        print(f"\n[ERROR] 启动失败: {e}")
        import traceback
        traceback.print_exc()
