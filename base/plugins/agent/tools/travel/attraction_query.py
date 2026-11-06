"""
景点查询工具
功能：查询目的地景点信息
"""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

from base.plugins.agent.tools.base import BaseTool
from base.plugins.agent.tools.registry import ToolRegistry


class AttractionQueryTool(BaseTool):
    """
    景点查询工具
    参数：
    - city: 城市
    - category: 景点类型（可选）：nature自然景观、culture文化古迹、shopping购物、food美食
    - rating: 最低评分（可选，1-5）
    - days: 游玩天数（用于推荐每日行程）
    """
    
    @staticmethod
    def execute(params: Dict[str, Any]) -> Dict[str, Any]:
        """执行景点查询"""
        try:
            city = params.get("city", "")
            category = params.get("category", "")
            rating = params.get("rating", 0)
            days = params.get("days", 3)
            
            logger.info(f"[Attraction Query] 查询景点: {city}, category={category}, days={days}")
            
            result = AttractionQueryTool._mock_search_attractions(
                city, category, rating, days
            )
            
            return {
                "success": True,
                "result": result,
                "message": "查询成功"
            }
            
        except Exception as e:
            logger.error(f"景点查询失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"查询失败: {str(e)}"
            }
    
    @staticmethod
    def _mock_search_attractions(city: str, category: str, rating: float, days: int) -> dict:
        """模拟景点查询"""
        
        mock_attractions = [
            {
                "id": "A001",
                "name": "外滩",
                "category": "nature",
                "city": city,
                "address": f"{city}黄浦区中山东一路",
                "rating": 4.9,
                "reviews": 12560,
                "price": 0,
                "duration": "2小时",
                "best_time": "傍晚",
                "tags": ["夜景", "拍照", "地标"],
                "description": f"{city}最著名的景点之一，可欣赏浦江两岸美景"
            },
            {
                "id": "A002",
                "name": "豫园",
                "category": "culture",
                "city": city,
                "address": f"{city}黄浦区豫园老街",
                "rating": 4.7,
                "reviews": 8900,
                "price": 40,
                "duration": "1.5小时",
                "best_time": "上午",
                "tags": ["园林", "历史", "文化"],
                "description": "江南古典园林的代表，已有400多年历史"
            },
            {
                "id": "A003",
                "name": "南京路步行街",
                "category": "shopping",
                "city": city,
                "address": f"{city}黄浦区南京东路",
                "rating": 4.5,
                "reviews": 15680,
                "price": 0,
                "duration": "3小时",
                "best_time": "下午",
                "tags": ["购物", "美食", "商业"],
                "description": "中国最繁华的商业街之一"
            },
            {
                "id": "A004",
                "name": "城隍庙",
                "category": "culture",
                "city": city,
                "address": f"{city}黄浦区方浜中路",
                "rating": 4.6,
                "reviews": 7890,
                "price": 10,
                "duration": "1小时",
                "best_time": "上午",
                "tags": ["宗教", "历史", "小吃"],
                "description": f"{city}重要的道教宫观，周边小吃众多"
            },
            {
                "id": "A005",
                "name": "陆家嘴金融中心",
                "category": "nature",
                "city": city,
                "address": f"{city}浦东新区世纪大道",
                "rating": 4.8,
                "reviews": 11230,
                "price": 0,
                "duration": "2小时",
                "best_time": "白天",
                "tags": ["现代建筑", "观景", "地标"],
                "description": "中国金融中心，可登东方明珠或上海中心俯瞰全城"
            },
            {
                "id": "A006",
                "name": "田子坊",
                "category": "food",
                "city": city,
                "address": f"{city}黄浦区泰康路",
                "rating": 4.4,
                "reviews": 9870,
                "price": 0,
                "duration": "2小时",
                "best_time": "下午",
                "tags": ["文艺", "小吃", "创意"],
                "description": "老上海弄堂改造的文艺街区，美食小吃聚集地"
            }
        ]
        
        filtered = []
        for attr in mock_attractions:
            if category and attr["category"] != category:
                continue
            if attr["rating"] < rating:
                continue
            filtered.append(attr)
        
        daily_itinerary = []
        attractions_per_day = (len(filtered) + days - 1) // days
        for day in range(days):
            start = day * attractions_per_day
            end = start + attractions_per_day
            day_attractions = filtered[start:end]
            daily_itinerary.append({
                "day": day + 1,
                "attractions": day_attractions
            })
        
        return {
            "attractions": filtered,
            "daily_itinerary": daily_itinerary,
            "total_count": len(filtered)
        }
    
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
                "category": {
                    "type": "string",
                    "enum": ["nature", "culture", "shopping", "food"],
                    "description": "景点类型：nature自然景观、culture文化古迹、shopping购物、food美食"
                },
                "rating": {
                    "type": "number",
                    "description": "最低评分（1-5）",
                    "default": 4.0
                },
                "days": {
                    "type": "integer",
                    "description": "游玩天数（用于生成每日行程）",
                    "default": 3
                }
            },
            "required": ["city"]
        }


ToolRegistry.register("attraction_query", AttractionQueryTool)