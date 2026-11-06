"""
亚马逊订单查询 - 工具（Tool）
单一职责：只负责查询亚马逊订单
"""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

from base.plugins.agent.tools.base import BaseTool
from base.plugins.agent.tools.registry import ToolRegistry


class AmazonOrderQueryTool(BaseTool):
    """
    亚马逊订单查询工具
    功能：根据订单ID或邮箱查询亚马逊订单
    """
    
    @staticmethod
    def execute(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行订单查询
        
        Args:
            params: 输入参数
                - order_id: 订单ID（可选）
                - customer_email: 客户邮箱（可选）
                - platform: 平台（us/uk/jp等，默认us）
                - days: 查询最近几天的天数（可选）
                - seller_id: 卖家ID（必需）
                
        Returns:
            查询结果
        """
        try:
            order_id = params.get("order_id", "")
            customer_email = params.get("customer_email", "")
            platform = params.get("platform", "us")
            days = params.get("days", 30)
            seller_id = params.get("seller_id", "")
            
            if not seller_id:
                return {"success": False, "message": "卖家ID不能为空"}
            
            logger.info(f"[Amazon Tool] 查询订单: order_id={order_id}, platform={platform}")
            
            # TODO: 这里调用真实的亚马逊 SP-API
            result = AmazonOrderQueryTool._mock_query_from_api(
                order_id=order_id,
                customer_email=customer_email,
                platform=platform,
                days=days,
                seller_id=seller_id
            )
            
            return {
                "success": True,
                "result": result,
                "message": "查询成功"
            }
            
        except Exception as e:
            logger.error(f"亚马逊订单查询失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"查询失败: {str(e)}"
            }
    
    @staticmethod
    def _mock_query_from_api(order_id: str, customer_email: str, 
                            platform: str, days: int, seller_id: str) -> list:
        """模拟从亚马逊 API 获取数据"""
        
        mock_data = [
            {
                "order_id": "123-4567890-1234567",
                "order_date": "2026-05-01",
                "status": "Shipped",
                "total": "$29.99",
                "items": ["Wireless Headphones"],
                "customer": "john@example.com"
            },
            {
                "order_id": "987-6543210-7654321",
                "order_date": "2026-05-03",
                "status": "Processing",
                "total": "$49.99",
                "items": ["Smart Watch"],
                "customer": "jane@example.com"
            }
        ]
        
        if order_id:
            mock_data = [o for o in mock_data if order_id in o["order_id"]]
        if customer_email:
            mock_data = [o for o in mock_data if customer_email.lower() in o["customer"].lower()]
            
        return mock_data
    
    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        """获取参数 Schema（用于 LLM 理解）"""
        return {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "订单ID，格式如 123-4567890-1234567"
                },
                "customer_email": {
                    "type": "string", 
                    "description": "客户邮箱"
                },
                "platform": {
                    "type": "string",
                    "enum": ["us", "uk", "jp", "de", "fr"],
                    "description": "站点：us美国、uk英国、jp日本等"
                },
                "days": {
                    "type": "integer",
                    "description": "查询最近几天的订单"
                },
                "seller_id": {
                    "type": "string",
                    "description": "卖家ID（必需）"
                }
            },
            "required": ["seller_id"]
        }


ToolRegistry.register("amazon_order_query", AmazonOrderQueryTool)

