"""
Tool（工具）基类
工具是单一、原子级别的操作
比如：查询订单、发送邮件、查询费用等
"""
from typing import Dict, Any


class BaseTool:
    """
    工具基类 - 单一职责，做一件具体的事
    """
    
    @staticmethod
    def execute(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具
        
        Args:
            params: 输入参数
            
        Returns:
            执行结果
        """
        raise NotImplementedError("子类必须实现 execute 方法")
    
    @classmethod
    def get_name(cls) -> str:
        """
        获取工具名称
        
        Returns:
            工具名称
        """
        return cls.__name__
    
    @classmethod
    def get_description(cls) -> str:
        """
        获取工具描述（用于 LLM 理解）
        
        Returns:
            工具描述
        """
        return cls.__doc__ or "No description"
    
    @classmethod
    def get_parameters_schema(cls) -> Dict[str, Any]:
        """
        获取参数 Schema（用于 LLM 理解）
        
        Returns:
            参数 Schema
        """
        return {}

