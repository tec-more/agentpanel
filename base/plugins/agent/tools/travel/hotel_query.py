"""
酒店查询工具
功能：查询目的地酒店信息
"""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

from base.plugins.agent.tools.base import BaseTool
from base.plugins.agent.tools.registry import ToolRegistry


class HotelQueryTool(BaseTool):
    """
    酒店查询工具
    参数：
    - city: 城市
    - checkin: 入住日期 (YYYY-MM-DD)
    - checkout: 退房日期 (YYYY-MM-DD)
    - guests: 入住人数 (默认2)
    - price_range: 价格范围 [min, max] (可选)
    - rating: 最低评分 (1-5) (可选)
    """
    
    @staticmethod
    def execute(params: Dict[str, Any]) -> Dict[str, Any]:
        """执行酒店查询"""
        try:
            city = params.get("city", "")
            checkin = params.get("checkin", "")
            checkout = params.get("checkout", "")
            guests = params.get("guests", 2)
            price_range = params.get("price_range", [0, 10000])
            rating = params.get("rating", 0)
            
            logger.info(f"[Hotel Query] 查询酒店: {city}, {checkin} ~ {checkout}")
            
            result = HotelQueryTool._mock_search_hotels(
                city, checkin, checkout, guests, price_range, rating
            )
            
            return {
                "success": True,
                "result": result,
                "message": "查询成功"
            }
            
        except Exception as e:
            logger.error(f"酒店查询失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"查询失败: {str(e)}"
            }
    
    @staticmethod
    def _mock_search_hotels(city: str, checkin: str, checkout: str, 
                          guests: int, price_range: list, rating: float) -> list:
        """模拟酒店查询"""
        
        # 示例酒店数据
        mock_hotels = [
            {
                "hotel_id": "H001",
                "name": "外滩华尔道夫酒店",
                "address": f"{city}黄浦区中山东一路2号",
                "stars": 5,
                "rating": 4.8,
                "reviews": 2345,
                "price_per_night": 1880,
                "amenities": ["WiFi", "游泳池", "健身房", "餐厅", "SPA"],
                "distance_to_center": "0.5km"
            },
            {
                "hotel_id": "H002",
                "name": "浦东丽思卡尔顿酒店",
                "address": f"{city}陆家嘴世纪大道8号",
                "stars": 5,
                "rating": 4.9,
                "reviews": 1876,
                "price_per_night": 2580,
                "amenities": ["WiFi", "游泳池", "健身房", "餐厅", "SPA", "行政酒廊"],
                "distance_to_center": "3km"
            },
            {
                "hotel_id": "H003",
                "name": "全季酒店",
                "address": f"{city}人民广场附近",
                "stars": 4,
                "rating": 4.5,
                "reviews": 5678,
                "price_per_night": 380,
                "amenities": ["WiFi", "早餐", "健身房"],
                "distance_to_center": "1.5km"
            },
            {
                "hotel_id": "H004",
                "name": "如家酒店",
                "address": f"{city}南京东路步行街旁",
                "stars": 3,
                "rating": 4.3,
                "reviews": 3456,
                "price_per_night": 180,
                "amenities": ["WiFi", "早餐"],
                "distance_to_center": "1km"
            }
        ]
        
        # 过滤价格和评分
        filtered_hotels = []
        min_price, max_price = price_range
        for hotel in mock_hotels:
            if (hotel["price_per_night"] >= min_price and 
                hotel["price_per_night"] <= max_price and 
                hotel["rating"] >= rating):
                filtered_hotels.append(hotel)
        
        return filtered_hotels
    
    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        """获取参数 Schema"""
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称"
                },
                "checkin": {
                    "type": "string",
                    "description": "入住日期，格式：YYYY-MM-DD"
                },
                "checkout": {
                    "type": "string",
                    "description": "退房日期，格式：YYYY-MM-DD"
                },
                "guests": {
                    "type": "integer",
                    "description": "入住人数，默认2",
                    "default": 2
                },
                "price_range": {
                    "type": "array",
                    "description": "价格范围 [最低价, 最高价]，如：[200, 2000]"
                },
                "rating": {
                    "type": "number",
                    "description": "最低评分（1-5），如：4.0"
                }
            },
            "required": ["city", "checkin", "checkout"]
        }


ToolRegistry.register("hotel_query", HotelQueryTool)
