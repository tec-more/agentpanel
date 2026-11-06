"""
消息模块 - WebSocket 连接管理器
按 user_id 维度管理连接，支持单用户多连接（多标签页场景）
"""
import json
from typing import Dict, Set
from fastapi import WebSocket
from loguru import logger


class MailConnectionManager:
    """按 user_id 维度管理 WebSocket 连接，支持单用户多连接（多标签页）"""

    def __init__(self):
        self._connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(user_id, set()).add(ws)
        logger.info(f"[mail.ws] 用户 #{user_id} 连接，当前在线 {len(self._connections)} 人")

    def disconnect(self, user_id: int, ws: WebSocket) -> None:
        conns = self._connections.get(user_id)
        if conns:
            conns.discard(ws)
            if not conns:
                del self._connections[user_id]
        logger.info(f"[mail.ws] 用户 #{user_id} 断开，当前在线 {len(self._connections)} 人")

    async def push_to_user(self, user_id: int, payload: dict) -> None:
        """向指定用户的所有连接推送 JSON 消息；自动清理失效连接"""
        conns = self._connections.get(user_id)
        if not conns:
            return
        text = json.dumps(payload, ensure_ascii=False)
        dead = []
        for ws in conns:
            try:
                await ws.send_text(text)
            except Exception as e:
                logger.warning(f"[mail.ws] 推送失败 user=#{user_id}: {e}")
                dead.append(ws)
        for ws in dead:
            conns.discard(ws)
            if not conns:
                self._connections.pop(user_id, None)

    async def push_to_users(self, user_ids: list, payload: dict) -> None:
        """向多个用户批量推送（每个用户共享同一 payload）"""
        for uid in user_ids:
            await self.push_to_user(uid, payload)

    def online_user_ids(self) -> list:
        return list(self._connections.keys())

    def online_count(self) -> int:
        return len(self._connections)


# 模块级单例，进程内共享
mail_ws_manager = MailConnectionManager()
