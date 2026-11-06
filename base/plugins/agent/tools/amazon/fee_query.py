"""
亚马逊费用查询 - 工具（Tool）
单一职责：只负责查询亚马逊费用
"""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

from base.plugins.agent.tools.base import BaseTool
from base.plugins.agent.tools.registry import ToolRegistry


class AmazonFeeQueryTool(BaseTool):
    """
    亚马逊费用查询工具
    功能：查询亚马逊订单费用、平台费用等
    """
    
    @staticmethod
    def execute(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行费用查询
        
        Args:
            params: 输入参数
                - order_id: 订单ID（可选）
                - start_date: 开始日期（格式：YYYY-MM-DD）
                - end_date: 结束日期（格式：YYYY-MM-DD）
                - platform: 平台（us/uk/jp等）
                - seller_id: 卖家ID（必需）
                
        Returns:
            查询结果
        """
        try:
            order_id = params.get("order_id", "")
            start_date = params.get("start_date", "")
            end_date = params.get("end_date", "")
            platform = params.get("platform", "us")
            seller_id = params.get("seller_id", "")
            
            if not seller_id:
                return {"success": False, "message": "卖家ID不能为空"}
            
            logger.info(f"[Amazon Tool] 查询费用: order_id={order_id}, date={start_date}~{end_date}")
            
            result = AmazonFeeQueryTool._mock_query_fee(
                order_id=order_id,
                start_date=start_date,
                end_date=end_date,
                platform=platform,
                seller_id=seller_id
            )
            
            return {
                "success": True,
                "result": result,
                "message": "查询成功"
            }
            
        except Exception as e:
            logger.error(f"费用查询失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"查询失败: {str(e)}"
            }
    
    @staticmethod
    def _mock_query_fee(order_id: str, start_date: str, end_date: str, 
                       platform: str, seller_id: str) -> dict:
        """模拟费用查询"""
        
        fee_details = {
            "summary": {
                "total_revenue": "$1,234.56",
                "total_fees": "$345.67",
                "net_profit": "$888.89"
            },
            "fees": [
                {"type": "Referral Fee", "amount": "$123.45", "description": "佣金"},
                {"type": "FBA Fee", "amount": "$89.12", "description": "物流配送费"},
                {"type": "Storage Fee", "amount": "$45.67", "description": "仓储费"},
                {"type": "Other", "amount": "$87.43", "description": "其他费用"}
            ]
        }
        
        return fee_details
    
    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        """获取参数 Schema"""
        return {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "订单ID"},
                "start_date": {"type": "string", "description": "开始日期，格式 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期，格式 YYYY-MM-DD"},
                "platform": {"type": "string", "description": "站点"},
                "seller_id": {"type": "string", "description": "卖家ID（必需）"}
            },
            "required": ["seller_id"]
        }


ToolRegistry.register("amazon_fee_query", AmazonFeeQueryTool)

