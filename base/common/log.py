import logging
import sys
import atexit
import json
from pathlib import Path
from typing_extensions import override
from loguru import logger
from base.common.setting import settings


# 全局变量记录日志处理器ID
_logger_handlers = []


def json_formatter(record):
    """JSON格式日志输出，用于ELK/EFK日志收集"""
    log_entry = {
        "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "level": record["level"].name,
        "logger": record["name"],
        "function": record["function"],
        "line": record["line"],
        "module": record["module"],
        "message": record["message"],
        "app_name": record.get("extra", {}).get("app_name", settings.app_name),
    }
    
    if record["extra"].get("trace_id"):
        log_entry["trace_id"] = record["extra"]["trace_id"]
    
    if record["extra"].get("user_id"):
        log_entry["user_id"] = record["extra"]["user_id"]
    
    if record["exception"]:
        log_entry["exception"] = {
            "type": record["exception"].__class__.__name__,
            "message": str(record["exception"]),
        }
    
    return json.dumps(log_entry) + "\n"


class InterceptHandler(logging.Handler):
    """
    日志拦截处理器：将所有 Python 标准日志重定向到 Loguru
    
    工作原理：
    1. 继承自 logging.Handler
    2. 重写 emit 方法处理日志记录
    3. 将标准库日志转换为 Loguru 格式
    """
    @override
    def emit(self, record: logging.LogRecord) -> None:
        # 尝试获取日志级别名称
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 获取调用帧信息，增加None检查
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        # 使用 Loguru 记录日志
        logger.opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage()
        )
        

def cleanup_logging():
    """
    清理日志资源
    在程序退出时调用,确保所有日志处理器被正确关闭
    """
    global _logger_handlers
    
    for handler_id in _logger_handlers:
        try:
            logger.remove(handler_id)
        except Exception:
            pass
    
    _logger_handlers.clear()


def setup_logging():
    """
    配置日志系统
    
    功能：
    1. 控制台彩色输出
    2. 文件日志轮转
    3. 错误日志单独存储
    4. 智能异步策略：开发环境同步(避免reload资源泄漏)，生产环境异步(高性能)
    """
    global _logger_handlers
    
    # 添加上下文信息
    _ = logger.configure(extra={"app_name": settings.app_name})
    # 步骤1：移除默认处理器
    logger.remove()

    # 步骤2：定义日志格式
    log_format = (
        # 时间信息
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        # 日志级别，居中对齐
        "<level>{level: <8}</level> | "
        # 文件、函数和行号
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        # 日志消息
        "<level>{message}</level>"
    )

    # 智能选择异步策略：开发环境禁用异步(避免reload时资源泄漏)，生产环境启用异步(提升性能)
    use_async = not settings.debug
    
    # 步骤3：配置控制台输出
    handler_id = logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG" if settings.debug else "INFO",
        enqueue=use_async,   # 开发同步,生产异步
        backtrace=True,      # 显示完整的异常回溯
        diagnose=True,       # 显示变量值等诊断信息
        colorize=True        # 启用彩色输出
    )
    _logger_handlers.append(handler_id)

    # 步骤4：创建日志目录
    log_dir = Path(settings.LOG_DIR)
    # 确保日志目录存在,如果不存在则创建
    log_dir.mkdir(parents=True, exist_ok=True)

    # 步骤5：配置常规日志文件
    handler_id = logger.add(
        str(log_dir / "info.log"),
        format=log_format,
        level="INFO",
        rotation="00:00",  # 每天午夜轮转
        retention=30,      # 日志保留天数，超过此天数的日志文件将被自动清理
        compression="gz",
        encoding="utf-8",
        enqueue=use_async  # 开发同步,生产异步
    )
    _logger_handlers.append(handler_id)

    # 步骤6：配置错误日志文件
    handler_id = logger.add(
        str(log_dir / "error.log"),
        format=log_format,
        level="ERROR",
        rotation="00:00",  # 每天午夜轮转
        retention=30,      # 日志保留天数，超过此天数的日志文件将被自动清理
        compression="gz",
        encoding="utf-8",
        enqueue=use_async, # 开发同步,生产异步
        backtrace=True,
        diagnose=True
    )
    _logger_handlers.append(handler_id)

    # 步骤6.5：配置JSON格式日志（用于ELK/EFK收集）
    elk_enabled = getattr(settings, 'ELK_ENABLED', False)
    if elk_enabled:
        handler_id = logger.add(
            str(log_dir / "app.json"),
            format=json_formatter,
            level="INFO",
            rotation="00:00",
            retention=30,
            compression="gz",
            encoding="utf-8",
            enqueue=use_async
        )
        _logger_handlers.append(handler_id)

    # 步骤7：配置标准库日志
    logging.basicConfig(handlers=[InterceptHandler()], level="DEBUG" if settings.debug else "INFO", force=True)
    logger_name_list = [name for name in logging.root.manager.loggerDict]
    
    # 步骤8：配置第三方库日志
    for logger_name in logger_name_list:
        _logger = logging.getLogger(logger_name)
        if logger_name in ['websockets.client', 'websockets.server', 'httpx', 'httpcore', 'tortoise']:
            _logger.setLevel(logging.WARNING)
        _logger.handlers = [InterceptHandler()]
        _logger.propagate = False

    _noisy_loggers = ['aiormq', 'aio_pika', 'pamqp']
    for noisy in _noisy_loggers:
        logging.getLogger(noisy).setLevel(logging.WARNING)
    
    # 注册退出清理函数
    atexit.register(cleanup_logging)

log = logger