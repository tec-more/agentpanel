from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
from base.common.setting import settings


class TracingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.tracer = trace.get_tracer(__name__)

    async def dispatch(self, request: Request, call_next):
        with self.tracer.start_as_current_span(f"{request.method} {request.url.path}"):
            response = await call_next(request)
            return response


def setup_jaeger():
    if not getattr(settings, 'JAEGER_ENABLED', False):
        return
    
    jaeger_host = getattr(settings, 'JAEGER_HOST', 'localhost')
    jaeger_port = getattr(settings, 'JAEGER_PORT', 6831)
    service_name = getattr(settings, 'app_name', 'aipaneladmin')
    
    resource = Resource(attributes={
        "service.name": service_name
    })
    
    trace.set_tracer_provider(TracerProvider(resource=resource))
    
    jaeger_exporter = JaegerExporter(
        agent_host_name=jaeger_host,
        agent_port=jaeger_port
    )
    
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )


def instrument_app(app):
    if not getattr(settings, 'JAEGER_ENABLED', False):
        return
    
    FastAPIInstrumentor.instrument_app(app)
    RequestsInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()