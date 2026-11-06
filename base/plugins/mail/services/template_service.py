"""
模板渲染服务 - 支持 {record_id} / {field_name} 简单占位符
"""
import re
from typing import Any, Optional


def render_template(template: Optional[str], record_id: Any = None, data: Optional[dict] = None,
                    before_data: Optional[dict] = None) -> str:
    """渲染简单模板。

    支持的占位符：
    - {record_id}              → record_id
    - {field_name}             → data[field_name]（after_data）
    - {old_field_name}         → before_data[field_name]
    - {field_name} 形式任意字段名

    Args:
        template: 模板字符串，None 或空字符串返回空串
        record_id: 记录ID
        data: 变更后数据（after_data）
        before_data: 变更前数据（before_data），用于 {old_xxx}
    """
    if not template:
        return ""
    data = data or {}
    before_data = before_data or {}

    def _replace(match):
        key = match.group(1)
        if key == "record_id":
            return str(record_id) if record_id is not None else ""
        if key.startswith("old_"):
            real_key = key[4:]
            val = before_data.get(real_key, "")
            return "" if val is None else str(val)
        val = data.get(key, "")
        return "" if val is None else str(val)

    return re.sub(r"\{(\w+)\}", _replace, template)
