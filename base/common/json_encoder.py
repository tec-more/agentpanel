import json
from datetime import datetime
from base.common.setting import settings


class DateTimeEncoder(json.JSONEncoder):
    """
    自定义 JSON 编码器，用于处理 datetime 对象
    将 datetime 对象转换为指定格式的字符串
    """
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime(settings.DATETIME_FORMAT)
        return super().default(obj)
