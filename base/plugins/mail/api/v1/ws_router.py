"""
消息模块 - WebSocket 实时推送路由
仿 base/plugins/llm/api/v1/voice_websocket.py 模式，需在 start.py:init_app() 手动注册
"""
import json
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from loguru import logger

from base.common.security import get_current_user_id_ws
from base.plugins.mail.services.ws_manager import mail_ws_manager
from base.plugins.mail.services.notification_service import NotificationService

ws_router = APIRouter(tags=["消息-WebSocket"])


@ws_router.websocket("/ws")
async def mail_ws(websocket: WebSocket, token: Optional[str] = Query(None)):
    """消息实时推送 WebSocket

    连接：ws://host/api/v1/mail/ws?token=<JWT>
    鉴权失败 → 服务端关闭连接（code=4401）

    服务端下发：
      {"type":"unread_count","unread_count":N}                     # 连接建立时初始未读数
      {"type":"notification","notification":{...},"message":{...},"unread_count":N}  # 新通知

    客户端可发：
      {"type":"ping"}  # 心跳，服务端回 {"type":"pong"}
    """
    user_id = await get_current_user_id_ws(token)
    if not user_id:
        await websocket.close(code=4401)
        return

    await mail_ws_manager.connect(user_id, websocket)
    try:
        # 推送初始未读数
        count = await NotificationService.get_unread_count(user_id)
        await websocket.send_text(json.dumps({
            "type": "unread_count",
            "unread_count": count,
        }, ensure_ascii=False))

        # 主循环：接收客户端消息（心跳/命令）
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"[mail.ws] 异常 user=#{user_id}: {e}")
    finally:
        mail_ws_manager.disconnect(user_id, websocket)
