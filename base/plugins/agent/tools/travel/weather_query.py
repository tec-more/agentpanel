"""
天气查询工具
功能：查询目的地天气预报
"""
from typing import Dict, Any
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

from base.plugins.agent.tools.base import BaseTool
from base.plugins.agent.tools.registry import ToolRegistry


class WeatherQueryTool(BaseTool):
    """
    天气查询工具
    参数：
    - city: 城市
    - days: 查询天数（默认7天）
    """
    
    @staticmethod
    def execute(params: Dict[str, Any]) -> Dict[str, Any]:
        """执行天气查询"""
        try:
            city = params.get("city", "")
            days = params.get("days", 7)
            
            logger.info(f"[Weather Query] 查询天气: {city}, {days}天")
            
            result = WeatherQueryTool._mock_get_weather(city, days)
            
            return {
                "success": True,
                "result": result,
                "message": "查询成功"
            }
            
        except Exception as e:
            logger.error(f"天气查询失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"查询失败: {str(e)}"
            }
    
    @staticmethod
    def _mock_get_weather(city: str, days: int) -> list:
        """模拟天气查询"""
        
        weather_types = ["晴", "多云", "阴", "小雨", "中雨", "雷阵雨", "晴转多云"]
        temperatures = {
            "北京": {"min": 15, "max": 28},
            "上海": {"min": 20, "max": 32},
            "广州": {"min": 25, "max": 35},
            "深圳": {"min": 26, "max": 34},
            "成都": {"min": 18, "max": 30},
            "default": {"min": 20, "max": 28}
        }
        
        base_temp = temperatures.get(city, temperatures["default"])
        
        forecast = []
        today = datetime.now()
        
        for i in range(days):
            date = today + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][date.weekday()]
            
            weather = weather_types[i % len(weather_types)]
            temp_variation = i - days // 2
            
            forecast.append({
                "date": date_str,
                "weekday": weekday,
                "weather": weather,
                "temperature": {
                    "min": base_temp["min"] + temp_variation - 2,
                    "max": base_temp["max"] + temp_variation + 2
                },
                "humidity": f"{55 + i * 3}%",
                "wind": f"{3 + i}级 {['东风', '南风', '西风', '北风'][i % 4]}",
                "aqi": f"{60 + i * 10} (良)",
                "tip": WeatherQueryTool._get_weather_tip(weather)
            })
        
        return forecast
    
    @staticmethod
    def _get_weather_tip(weather: str) -> str:
        """获取天气提示"""
        tips = {
            "晴": "天气晴好，适合外出游玩，记得做好防晒！",
            "多云": "多云天气，温度适中，适合各种活动。",
            "阴": "阴天，可能会有些闷，建议多喝水。",
            "小雨": "有小雨，出门记得带伞，路滑注意安全。",
            "中雨": "中雨，尽量避免外出，如需外出记得带伞。",
            "雷阵雨": "雷阵雨天气，请避免在户外停留，注意避雷。",
            "晴转多云": "晴转多云，天气变化快，建议带薄外套备用。"
        }
        return tips.get(weather, "今天天气不错，祝您心情愉快！")
    
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
                "days": {
                    "type": "integer",
                    "description": "查询天数，默认7天",
                    "default": 7
                }
            },
            "required": ["city"]
        }


ToolRegistry.register("weather_query", WeatherQueryTool)
