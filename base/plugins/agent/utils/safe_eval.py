"""
安全的表达式求值工具
使用 simpleeval 替代危险的 eval()
"""
import logging
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)

try:
    from simpleeval import simple_eval, SimpleEval
    SIMPLEEVAL_AVAILABLE = True
except ImportError:
    SIMPLEEVAL_AVAILABLE = False


class SafeEval:
    """
    安全的表达式求值类
    """
    
    @staticmethod
    def evaluate(
        expression: str,
        variables: Optional[Dict[str, Any]] = None,
        functions: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        安全地求值表达式
        
        Args:
            expression: 表达式字符串
            variables: 变量字典
            functions: 函数字典
            
        Returns:
            求值结果
            
        Raises:
            Exception: 求值失败时抛出
        """
        variables = variables or {}
        functions = functions or {}
        
        if SIMPLEEVAL_AVAILABLE:
            return SafeEval._evaluate_with_simpleeval(
                expression, variables, functions
            )
        else:
            logger.warning("simpleeval 不可用，使用受限的 eval()")
            return SafeEval._evaluate_with_limited_eval(
                expression, variables, functions
            )
    
    @staticmethod
    def _evaluate_with_simpleeval(
        expression: str,
        variables: Dict[str, Any],
        functions: Dict[str, Any]
    ) -> Any:
        """
        使用 simpleeval 求值
        
        Args:
            expression: 表达式字符串
            variables: 变量字典
            functions: 函数字典
            
        Returns:
            求值结果
        """
        # 创建求值器
        evaluator = SimpleEval()
        
        # 添加变量
        evaluator.names.update(variables)
        
        # 添加常用函数
        default_functions = {
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "max": max,
            "min": min,
        }
        evaluator.functions.update(default_functions)
        
        # 添加自定义函数
        evaluator.functions.update(functions)
        
        # 求值
        return evaluator.eval(expression)
    
    @staticmethod
    def _evaluate_with_limited_eval(
        expression: str,
        variables: Dict[str, Any],
        functions: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        使用受限的 eval() 求值（备选方案）
        
        Args:
            expression: 表达式字符串
            variables: 变量字典
            functions: 函数字典
            
        Returns:
            求值结果
        """
        functions = functions or {}
        
        # 限制 globals
        safe_globals = {
            "__builtins__": {
                "True": True,
                "False": False,
                "None": None,
                "int": int,
                "float": float,
                "str": str,
                "bool": bool,
                "len": len,
            }
        }
        
        # 将函数合并到变量中，供 eval 使用
        local_vars = variables.copy()
        local_vars.update(functions)
        
        # 支持 JavaScript 风格的布尔值（true/false）和运算符（||, &&, !）
        import re
        original_expression = expression
        
        # 移除换行符和多余空格，避免语法错误
        expression = expression.replace('\n', ' ').replace('\r', ' ')
        expression = re.sub(r'\s+', ' ', expression).strip()
        
        expression = re.sub(r'\btrue\b', 'True', expression)
        expression = re.sub(r'\bfalse\b', 'False', expression)
        
        # 转换 JavaScript 逻辑运算符
        expression = expression.replace('||', ' or ')
        expression = expression.replace('&&', ' and ')
        
        # 转换 JavaScript 取反运算符（注意空格处理）
        expression = re.sub(r'(!)(\w+)', r' not \2', expression)
        
        # 添加调试信息
        logger.debug(f"[safe_eval] 原始表达式: {original_expression}")
        logger.debug(f"[safe_eval] 转换后表达式: {expression}")
        logger.debug(f"[safe_eval] 可用变量: {list(local_vars.keys())}")
        
        try:
            return eval(expression, safe_globals, local_vars)
        except SyntaxError as e:
            logger.error(f"[safe_eval] 语法错误: {e}, 表达式: {expression}")
            raise
        except Exception as e:
            logger.error(f"[safe_eval] 执行错误: {e}, 表达式: {expression}")
            raise
    
    @staticmethod
    def evaluate_condition(
        expression: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        求值条件表达式，返回布尔值
        
        Args:
            expression: 条件表达式
            variables: 变量字典
            
        Returns:
            布尔值
        """
        try:
            result = SafeEval.evaluate(expression, variables)
            return bool(result)
        except Exception as e:
            logger.warning(f"条件求值失败: {expression}, 错误: {e}")
            return False


# 便捷函数
def safe_eval(
    expression: str,
    variables: Optional[Dict[str, Any]] = None,
    functions: Optional[Dict[str, Any]] = None
) -> Any:
    """
    便捷函数：安全求值
    
    Args:
        expression: 表达式字符串
        variables: 变量字典
        functions: 函数字典
        
    Returns:
        求值结果
    """
    return SafeEval.evaluate(expression, variables, functions)


def safe_eval_condition(
    expression: str,
    variables: Optional[Dict[str, Any]] = None
) -> bool:
    """
    便捷函数：安全求值条件
    
    Args:
        expression: 条件表达式
        variables: 变量字典
        
    Returns:
        布尔值
    """
    return SafeEval.evaluate_condition(expression, variables)


class ListOperations:
    """
    安全的列表操作工具类
    用于过滤、映射、排序等列表操作
    """
    
    @staticmethod
    def filter_list(
        lst: List[Any],
        filter_expr: str,
        item_var_name: str = "item"
    ) -> List[Any]:
        """
        安全地过滤列表
        
        Args:
            lst: 要过滤的列表
            filter_expr: 过滤表达式（使用 item 变量）
            item_var_name: 项变量名
            
        Returns:
            过滤后的列表
        """
        result = []
        for item in lst:
            try:
                if safe_eval_condition(
                    filter_expr,
                    {item_var_name: item}
                ):
                    result.append(item)
            except Exception as e:
                logger.warning(f"列表过滤跳过项: {item}, 错误: {e}")
                continue
        return result
    
    @staticmethod
    def map_list(
        lst: List[Any],
        map_expr: str,
        item_var_name: str = "item"
    ) -> List[Any]:
        """
        安全地映射列表
        
        Args:
            lst: 要映射的列表
            map_expr: 映射表达式（使用 item 变量）
            item_var_name: 项变量名
            
        Returns:
            映射后的列表
        """
        result = []
        for item in lst:
            try:
                mapped = safe_eval(
                    map_expr,
                    {item_var_name: item}
                )
                result.append(mapped)
            except Exception as e:
                logger.warning(f"列表映射跳过项: {item}, 错误: {e}")
                result.append(item)
        return result
    
    @staticmethod
    def sort_list(
        lst: List[Any],
        sort_key_expr: Optional[str] = None,
        item_var_name: str = "item"
    ) -> List[Any]:
        """
        安全地排序列表
        
        Args:
            lst: 要排序的列表
            sort_key_expr: 排序键表达式（使用 item 变量）
            item_var_name: 项变量名
            
        Returns:
            排序后的列表
        """
        if not sort_key_expr:
            return sorted(lst)
        
        try:
            def key_func(item):
                return safe_eval(
                    sort_key_expr,
                    {item_var_name: item}
                )
            
            return sorted(lst, key=key_func)
        except Exception as e:
            logger.warning(f"列表排序失败: {e}, 使用默认排序")
            return sorted(lst)


# 便捷函数
def safe_filter_list(
    lst: List[Any],
    filter_expr: str,
    item_var_name: str = "item"
) -> List[Any]:
    """
    便捷函数：安全过滤列表
    
    Args:
        lst: 要过滤的列表
        filter_expr: 过滤表达式
        item_var_name: 项变量名
        
    Returns:
        过滤后的列表
    """
    return ListOperations.filter_list(lst, filter_expr, item_var_name)


def safe_map_list(
    lst: List[Any],
    map_expr: str,
    item_var_name: str = "item"
) -> List[Any]:
    """
    便捷函数：安全映射列表
    
    Args:
        lst: 要映射的列表
        map_expr: 映射表达式
        item_var_name: 项变量名
        
    Returns:
        映射后的列表
    """
    return ListOperations.map_list(lst, map_expr, item_var_name)


def safe_sort_list(
    lst: List[Any],
    sort_key_expr: Optional[str] = None,
    item_var_name: str = "item"
) -> List[Any]:
    """
    便捷函数：安全排序列表
    
    Args:
        lst: 要排序的列表
        sort_key_expr: 排序键表达式
        item_var_name: 项变量名
        
    Returns:
        排序后的列表
    """
    return ListOperations.sort_list(lst, sort_key_expr, item_var_name)
