"""网关日志：独立 sink（component=gateway），不与业务请求日志混写。"""
from loguru import logger

from base.common.gateway.constants import GATEWAY_LOG_COMPONENT

gateway_logger = logger.bind(component=GATEWAY_LOG_COMPONENT)
