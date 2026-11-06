"""
模拟实时翻译服务（用于测试）
在没有网络连接时模拟豆包AST的响应
"""
import asyncio
import logging
from typing import AsyncIterator, Dict

logger = logging.getLogger(__name__)

class MockDoubaoASTService:
    """模拟豆包AST服务 - 用于测试实时翻译功能"""

    def __init__(self, app_key: str, access_key: str = None, **kwargs):
        self.app_key = app_key
        self.access_key = access_key

    async def streaming_translation(
        self,
        audio_data: bytes,
        source_language: str = "zh",
        target_language: str = "en",
        format: str = "wav",
        sample_rate: int = 16000
    ) -> AsyncIterator[Dict]:
        """
        模拟实时翻译

        模拟豆包AST的响应格式，用于测试实时翻译功能
        """
        logger.info(f"[MOCK] 模拟翻译开始: {len(audio_data)} bytes")

        # 模拟会话建立
        yield {
            "event": "session_started",
            "message": "模拟会话已建立"
        }

        # 模拟处理延迟
        await asyncio.sleep(0.5)

        # 模拟实时翻译结果（每隔几块返回一个）
        chunks_count = len(audio_data) // 3200  # 估算块数
        mock_translations = [
            {"source": "你好", "target": "Hello"},
            {"source": "世界", "target": "World"},
            {"source": "测试", "target": "Test"},
        ]

        for i, trans in enumerate(mock_translations):
            await asyncio.sleep(0.3)  # 模拟处理延迟
            yield {
                "event": "intermediate_result",
                "source_subtitle": {"text": trans["source"]},
                "target_subtitle": {"text": trans["target"]},
                "timestamp": 1234567890 + i * 1000
            }
            logger.info(f"[MOCK] 实时翻译: {trans['source']} -> {trans['target']}")

        # 模拟最终结果
        await asyncio.sleep(0.5)
        final_source = "你好世界测试"
        final_target = "Hello World Test"

        yield {
            "event": "session_finished",
            "source_subtitle": {"text": final_source},
            "target_subtitle": {"text": final_target},
            "response_meta": {
                "timestamp": 1234567890,
                "message": "Success"
            }
        }

        logger.info(f"[MOCK] 模拟翻译完成: {final_source} -> {final_target}")
