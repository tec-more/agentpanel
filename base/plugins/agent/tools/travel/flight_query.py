"""
航班查询工具
功能：查询可用航班信息
"""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

from base.plugins.agent.tools.base import BaseTool
from base.plugins.agent.tools.registry import ToolRegistry


class FlightQueryTool(BaseTool):
    """
    航班查询工具
    参数：
    - from_city: 出发城市
    - to_city: 目的地城市
    - date: 出发日期 (YYYY-MM-DD)
    - return_date: 返回日期 (可选)
    - passengers: 乘客人数 (默认1)
    - travel_class: 舱位 (economy/business/first)
    """
    
    @staticmethod
    def execute(params: Dict[str, Any]) -> Dict[str, Any]:
        """执行航班查询"""
        try:
            from_city = params.get("from_city", "")
            to_city = params.get("to_city", "")
            date = params.get("date", "")
            return_date = params.get("return_date", "")
            passengers = params.get("passengers", 1)
            travel_class = params.get("travel_class", "economy")
            
            logger.info(f"[Flight Query] 查询航班: {from_city} → {to_city}")
            
            result = FlightQueryTool._mock_search_flights(
                from_city, to_city, date, passengers, travel_class
            )
            
            return {
                "success": True,
                "result": result,
                "message": "查询成功"
            }
            
        except Exception as e:
            logger.error(f"航班查询失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"查询失败: {str(e)}"
            }
    
    @staticmethod
    def _mock_search_flights(from_city: str, to_city: str, date: str, 
                           passengers: int, travel_class: str) -> list:
        """模拟航班查询"""
        
        # 示例航班数据
        mock_flights = [
            {
                "flight_id": "CA1234",
                "airline": "中国国航",
                "from_city": from_city,
                "to_city": to_city,
                "departure_time": "08:30",
                "arrival_time": "11:45",
                "duration": "3h15m",
                "price": {
                    "economy": 1280,
                    "business": 3280,
                    "first": 6880
                },
                "available_seats": 25
            },
            {
                "flight_id": "CZ5678",
                "airline": "南方航空",
                "from_city": from_city,
                "to_city": to_city,
                "departure_time": "14:00",
                "arrival_time": "17:15",
                "duration": "3h15m",
                "price": {
                    "economy": 980,
                    "business": 2880,
                    "first": 5680
                },
                "available_seats": 18
            },
            {
                "flight_id": "MU9012",
                "airline": "东方航空",
                "from_city": from_city,
                "to_city": to_city,
                "departure_time": "19:30",
                "arrival_time": "22:45",
                "duration": "3h15m",
                "price": {
                    "economy": 880,
                    "business": 2580,
                    "first": 4980
                },
                "available_seats": 32
            }
        ]
        
        # 根据舱位过滤价格
        for flight in mock_flights:
            flight["price"] = flight["price"][travel_class]
        
        return mock_flights
    
    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        """获取参数 Schema"""
        return {
            "type": "object",
            "properties": {
                "from_city": {
                    "type": "string",
                    "description": "出发城市，如：北京、上海、广州"
                },
                "to_city": {
                    "type": "string",
                    "description": "目的地城市"
                },
                "date": {
                    "type": "string",
                    "description": "出发日期，格式：YYYY-MM-DD"
                },
                "return_date": {
                    "type": "string",
                    "description": "返回日期（可选），格式：YYYY-MM-DD"
                },
                "passengers": {
                    "type": "integer",
                    "description": "乘客人数，默认1",
                    "default": 1
                },
                "travel_class": {
                    "type": "string",
                    "enum": ["economy", "business", "first"],
                    "description": "舱位：economy经济舱、business商务舱、first头等舱"
                }
            },
            "required": ["from_city", "to_city", "date"]
        }


ToolRegistry.register("flight_query", FlightQueryTool)
