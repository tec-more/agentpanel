"""兼容 shim：实现已迁至共享包 `packages.agentpanel_common.domain.pricing_service`。

禁止在本文件再定义业务逻辑；既有 import 路径保持不变。
"""
from packages.agentpanel_common.domain.pricing_service import *  # noqa: F401,F403
