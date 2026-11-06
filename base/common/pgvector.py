"""
pgvector 支持模块
提供向量相关的辅助功能和 Tortoise ORM 自定义字段
"""
from typing import List, Optional, Any
from tortoise.fields import Field


class VectorField(Field):
    """
    pgvector 向量字段类型
    存储和查询浮点数向量
    """
    
    SQL_TYPE = "VECTOR"
    
    def __init__(
        self,
        dimension: int,
        **kwargs: Any
    ):
        self.dimension = dimension
        super().__init__(**kwargs)
    
    def to_db_value(
        self,
        value: Optional[List[float]],
        instance: Any
    ) -> Optional[str]:
        """
        将 Python 向量列表转换为 PostgreSQL 向量字符串
        """
        if value is None:
            return None
        
        # 验证向量维度
        if len(value) != self.dimension:
            raise ValueError(
                f"向量维度不匹配: 期望 {self.dimension}, 实际 {len(value)}"
            )
        
        # 使用 pgvector 的格式: [x, y, z]
        vector_str = "[" + ",".join([f"{v:.10f}" for v in value]) + "]"
        return vector_str
    
    def to_python_value(
        self,
        value: Optional[Any]
    ) -> Optional[List[float]]:
        """
        将数据库值转换为 Python 向量列表
        """
        if value is None:
            return None
        
        if isinstance(value, str):
            # 解析 pgvector 格式 [x, y, z]
            if value.startswith("[") and value.endswith("]"):
                try:
                    cleaned = value.strip("[]")
                    parts = cleaned.split(",")
                    return [float(p.strip()) for p in parts if p.strip()]
                except:
                    pass
        
        return value


def format_vector_for_sql(vector: List[float]) -> str:
    """
    将向量列表格式化为 pgvector 字符串
    """
    return "[" + ",".join([f"{v:.10f}" for v in vector]) + "]"


def cosine_distance_sql(vector_column: str, query_vector: List[float]) -> str:
    """
    生成用于 ORDER BY 的余弦距离 SQL
    """
    vector_str = format_vector_for_sql(query_vector)
    return f"{vector_column} <=> '{vector_str}'"
