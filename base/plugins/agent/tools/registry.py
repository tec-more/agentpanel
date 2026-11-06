"""
Tool（工具）注册表
"""
from typing import Dict, Type, Optional
import importlib
import os
import pkgutil


class ToolRegistry:
    """工具注册表"""
    _tools: Dict[str, Type] = {}
    
    @classmethod
    def register(cls, tool_type: str, tool_class: Type) -> None:
        """
        注册工具
        
        Args:
            tool_type: 工具类型
            tool_class: 工具类
        """
        cls._tools[tool_type] = tool_class
    
    @classmethod
    def get_tool(cls, tool_type: str) -> Optional[Type]:
        """
        获取工具类
        
        Args:
            tool_type: 工具类型
            
        Returns:
            工具类
        """
        return cls._tools.get(tool_type)
    
    @classmethod
    def get_tool_types(cls) -> list:
        """
        获取所有工具类型
        
        Returns:
            工具类型列表
        """
        return list(cls._tools.keys())
    
    @classmethod
    def is_tool_registered(cls, tool_type: str) -> bool:
        """
        检查工具是否已注册
        
        Args:
            tool_type: 工具类型
            
        Returns:
            是否已注册
        """
        return tool_type in cls._tools
    
    @classmethod
    def get_all_tools_info(cls) -> Dict[str, Dict[str, str]]:
        """
        获取所有工具的信息（用于 LLM 选择）
        
        Returns:
            工具信息字典
        """
        tools_info = {}
        for tool_type, tool_class in cls._tools.items():
            tools_info[tool_type] = {
                "name": tool_class.get_name(),
                "description": tool_class.get_description(),
                "parameters_schema": tool_class.get_parameters_schema()
            }
        return tools_info
    
    @classmethod
    async def auto_register_all(cls) -> None:
        """
        自动注册所有工具
        """
        current_dir = os.path.dirname(__file__)
        
        # 注册顶级目录的工具
        for _, module_name, _ in pkgutil.iter_modules([current_dir]):
            if module_name in ['base', 'registry']:
                continue
            try:
                module = importlib.import_module(f'base.plugins.agent.tools.{module_name}')
            except Exception as e:
                print(f"Error importing tool module {module_name}: {e}")
        
        # 注册子目录的工具（按平台组织）
        subdirs = [d for d in os.listdir(current_dir) 
                   if os.path.isdir(os.path.join(current_dir, d)) 
                   and not d.startswith('__')]
        
        for subdir in subdirs:
            subdir_path = os.path.join(current_dir, subdir)
            for _, module_name, _ in pkgutil.iter_modules([subdir_path]):
                try:
                    module = importlib.import_module(f'base.plugins.agent.tools.{subdir}.{module_name}')
                except Exception as e:
                    print(f"Error importing tool module {subdir}.{module_name}: {e}")

