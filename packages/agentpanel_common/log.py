"""共享日志配置（不读 L2 的 `settings`，由调用方注入参数）。

L2 仍以原有 `setup_logging()` 行为运行；L3 入口传入自己的 app 名/日志目录。
"""
import atexit
import json
import logging
import sys
from pathlib import Path

from loguru import logger
from typing_extensions import override

from services.gateway.gateway.constants import GATEWAY_LOG_COMPONENT

_logger_handlers = []
_app_name = "AIPanelAdmin"


def _is_gateway_record(record) -> bool:
    """网关日志（logger.bind(component=gateway)）单独归档，不混入业务请求日志。"""
    return record["extra"].get("component") == GATEWAY_LOG_COMPONENT


def json_formatter(record):
    """JSON 格式日志输出，用于 ELK/EFK 日志收集。"""
    log_entry = {
        "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "level": record["level"].name,
        "logger": record["name"],
        "function": record["function"],
        "line": record["line"],
        "module": record["module"],
        "message": record["message"],
        "app_name": record.get("extra", {}).get("app_name", _app_name),
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
    """将所有标准库日志重定向到 Loguru。"""

    @override
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def cleanup_logging():
    global _logger_handlers
    for handler_id in _logger_handlers:
        try:
            logger.remove(handler_id)
        except Exception:
            pass
    _logger_handlers.clear()


def setup_logging(
    *,
    app_name: str = "AIPanelAdmin",
    debug: bool = True,
    log_dir: str | Path | None = None,
    elk_enabled: bool = False,
    level: str | None = None,
):
    """配置日志系统（控制台 + info/error/gateway 文件 + 可选 JSON）。"""
    global _logger_handlers, _app_name
    _app_name = app_name

    logger.configure(extra={"app_name": app_name})
    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    use_async = not debug
    base_level = level or ("DEBUG" if debug else "INFO")

    handler_id = logger.add(
        sys.stdout,
        format=log_format,
        level=base_level,
        enqueue=use_async,
        backtrace=True,
        diagnose=True,
        colorize=True,
    )
    _logger_handlers.append(handler_id)

    if log_dir is None:
        log_dir = Path(__file__).resolve().parents[2] / "logs"
    target_dir = Path(log_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename, filter_fn, file_level in (
        ("info.log", lambda record: not _is_gateway_record(record), "INFO"),
        ("error.log", lambda record: not _is_gateway_record(record), "ERROR"),
        ("gateway.log", _is_gateway_record, "INFO"),
    ):
        handler_id = logger.add(
            str(target_dir / filename),
            format=log_format,
            level=file_level,
            filter=filter_fn,
            rotation="00:00",
            retention=30,
            compression="gz",
            encoding="utf-8",
            enqueue=use_async,
            backtrace=True,
            diagnose=True,
        )
        _logger_handlers.append(handler_id)

    if elk_enabled:
        handler_id = logger.add(
            str(target_dir / "app.json"),
            format=json_formatter,
            level="INFO",
            rotation="00:00",
            retention=30,
            compression="gz",
            encoding="utf-8",
            enqueue=use_async,
        )
        _logger_handlers.append(handler_id)

    logging.basicConfig(
        handlers=[InterceptHandler()],
        level="DEBUG" if debug else "INFO",
        force=True,
    )
    logger_name_list = [name for name in logging.root.manager.loggerDict]

    for logger_name in logger_name_list:
        one_logger = logging.getLogger(logger_name)
        if logger_name in ["websockets.client", "websockets.server", "httpx", "httpcore", "tortoise"]:
            one_logger.setLevel(logging.WARNING)
        one_logger.handlers = [InterceptHandler()]
        one_logger.propagate = False

    for noisy in ["aiormq", "aio_pika", "pamqp"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    atexit.register(cleanup_logging)


log = logger
