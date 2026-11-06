from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseEventHandler(ABC):
    """事件处理器基类"""

    enabled: bool = True
    priority: int = 100

    @abstractmethod
    async def handle(self, event_name: str, **kwargs):
        """处理事件"""
        pass

    def is_enabled(self) -> bool:
        """检查是否启用"""
        return self.enabled

    def get_priority(self) -> int:
        """获取优先级"""
        return self.priority