from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST, push_to_gateway
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
import time
import os
import asyncio
from typing import Dict, Callable

try:
    import psutil
except ImportError:
    psutil = None


# 全局注册表和指标
registry = CollectorRegistry()

# 全局指标
request_counter = Counter(
    'http_requests_total',
    'Total HTTP Requests',
    ['method', 'endpoint', 'status_code'],
    registry=registry
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP Request Duration',
    ['method', 'endpoint'],
    registry=registry,
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

active_requests = Gauge(
    'http_active_requests',
    'Active HTTP Requests',
    registry=registry
)

response_size = Histogram(
    'http_response_size_bytes',
    'HTTP Response Size',
    ['method', 'endpoint'],
    registry=registry
)

# 系统资源指标
process_cpu_percent = Gauge(
    'process_cpu_percent',
    'Process CPU usage percent',
    registry=registry
)

process_memory_rss = Gauge(
    'process_memory_rss_bytes',
    'Process RSS memory in bytes',
    registry=registry
)

process_memory_vms = Gauge(
    'process_memory_vms_bytes',
    'Process VMS memory in bytes',
    registry=registry
)

system_cpu_percent = Gauge(
    'system_cpu_percent',
    'System-wide CPU usage percent',
    registry=registry
)

system_memory_used = Gauge(
    'system_memory_used_bytes',
    'System memory used in bytes',
    registry=registry
)

system_memory_available = Gauge(
    'system_memory_available_bytes',
    'System memory available in bytes',
    registry=registry
)

_system_process = None


def get_process():
    global _system_process
    if psutil is None:
        raise ImportError("psutil not installed")
    if _system_process is None:
        _system_process = psutil.Process()
    return _system_process


def update_system_metrics():
    """更新系统资源指标"""
    try:
        process = get_process()
        
        # 进程指标
        process_cpu_percent.set(process.cpu_percent())
        mem_info = process.memory_info()
        process_memory_rss.set(mem_info.rss)
        process_memory_vms.set(mem_info.vms)
        
        # 系统指标
        system_cpu_percent.set(psutil.cpu_percent())
        mem = psutil.virtual_memory()
        system_memory_used.set(mem.used)
        system_memory_available.set(mem.available)
    except Exception:
        pass


class PrometheusMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method
        endpoint = request.url.path
        
        if endpoint == '/metrics':
            return await call_next(request)
        
        active_requests.inc()
        start_time = time.time()
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            content_length = int(response.headers.get('content-length', 0))
        except Exception as e:
            status_code = 500
            content_length = 0
            raise
        finally:
            duration = time.time() - start_time
            active_requests.dec()
            request_counter.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
            request_duration.labels(method=method, endpoint=endpoint).observe(duration)
            response_size.labels(method=method, endpoint=endpoint).observe(content_length)
        
        return response


async def metrics_endpoint(request: Request) -> Response:
    from base.common.setting import settings
    
    if not getattr(settings, 'PROMETHEUS_ENABLED', False):
        return Response(status_code=404, content="Prometheus endpoint not enabled")
    
    update_system_metrics()
    data = generate_latest(registry)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


def push_metrics():
    """推送指标到 Pushgateway"""
    from base.common.setting import settings
    from loguru import logger
    
    if not getattr(settings, 'PROMETHEUS_PUSH_ENABLED', False):
        return
    
    pushgateway_url = getattr(settings, 'PROMETHEUS_PUSHGATEWAY', 'localhost:9091')
    job_name = getattr(settings, 'app_name', 'aipaneladmin')
    
    try:
        push_to_gateway(
            pushgateway_url,
            job=job_name,
            registry=registry
        )
        logger.debug(f"Metrics pushed to Pushgateway: {pushgateway_url}")
    except Exception as e:
        logger.error(f"Failed to push metrics to Pushgateway: {e}")


async def start_push_worker():
    """启动定时推送任务"""
    from base.common.setting import settings
    from loguru import logger
    
    if not getattr(settings, 'PROMETHEUS_PUSH_ENABLED', False):
        return
    
    push_interval = getattr(settings, 'PROMETHEUS_PUSH_INTERVAL', 10)
    logger.info(f"Starting Prometheus push worker, interval: {push_interval}s")
    
    while True:
        try:
            push_metrics()
        except Exception as e:
            logger.error(f"Error in push worker: {e}")
        
        await asyncio.sleep(push_interval)
