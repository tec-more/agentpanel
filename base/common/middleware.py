import os
import importlib
import pkgutil
import inspect
from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp
from starlette.middleware.base import BaseHTTPMiddleware
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
from .setting import settings

class CustomCORSMiddleware(CORSMiddleware):
    """CORS跨域中间件"""
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(
            app,
            allow_origins=settings.ALLOW_ORIGINS,
            allow_methods=settings.ALLOW_METHODS,
            allow_headers=settings.ALLOW_HEADERS,
            allow_credentials=settings.ALLOW_CREDENTIALS,
            expose_headers=settings.CORS_EXPOSE_HEADERS,
        )

class MiddlewareAutoDiscover:
    """中间件自动发现和注册类 - 支持多模块"""
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.registered_middleware = []
    
    def auto_discover_all_modules(self, base_packages: List[str] = ["base.core", "base.plugins"]) -> List[Dict]:
        """
        自动发现所有业务模块中的中间件
        
        Args:
            base_package: 基础包名
            
        Returns:
            注册的中间件信息列表
        """
        try:
            all_middleware = []
            for base_package in base_packages:
                base_module = importlib.import_module(base_package)
                base_path = Path(base_module.__path__[0])
                
                print(f"[SCAN] Starting scan base package: {base_package}")
                print(f"[PATH] Base path: {base_path}")
                
                # 获取所有业务模块（users, dept等）
                business_modules = []
                for item in base_path.iterdir():
                    if item.is_dir() and not item.name.startswith('_') and item.name != '__pycache__':
                        # 检查是否有middleware目录
                        middleware_dir = item / "middleware"
                        if middleware_dir.exists() and middleware_dir.is_dir():
                            business_modules.append(item.name)
                
                print(f"[MODULES] Found business modules: {business_modules}")
                
                
                
                # 扫描每个业务模块的middleware目录
                for module_name in business_modules:
                    middleware_package = f"{base_package}.{module_name}.middleware"
                    module_middleware = self._discover_module_middleware(middleware_package, module_name)
                    all_middleware.extend(module_middleware)
                
                # 按优先级排序并注册
                all_middleware.sort(key=lambda x: x.get('priority', 999))
                self._register_middlewares(all_middleware)
            
            return all_middleware
            
        except ImportError as e:
            print(f"[ERROR] Failed to import base package {base_package}: {e}")
            return []
    
    def _discover_module_middleware(self, middleware_package: str, module_name: str) -> List[Dict]:
        """发现单个业务模块中的中间件"""
        module_middleware = []
        
        try:
            middleware_module = importlib.import_module(middleware_package)
            middleware_path = Path(middleware_module.__file__).parent
            
            print(f"  [SCAN] Scanning module: {module_name} -> {middleware_path}")
            
            # 扫描middleware目录下的所有Python文件
            for file_path in middleware_path.iterdir():
                if (file_path.is_file() and 
                    file_path.suffix == ".py" and 
                    not file_path.name.startswith('_') and
                    file_path.name != "__init__.py"):
                    
                    middleware_file_name = file_path.stem
                    full_module_path = f"{middleware_package}.{middleware_file_name}"
                    
                    try:
                        middleware_module = importlib.import_module(full_module_path)
                        middleware_info = self._extract_middleware(middleware_module, middleware_file_name, module_name)
                        
                        if middleware_info:
                            module_middleware.append(middleware_info)
                            print(f"    [OK] Found middleware: {module_name}.{middleware_file_name}")
                            
                    except ImportError as e:
                        print(f"    ⚠️ 导入失败: {full_module_path} -> {e}")
                        
        except ImportError:
            print(f"    ⚠️ 模块 {module_name} 没有middleware目录或导入失败")
            
        return module_middleware
    
    def _extract_middleware(self, module, file_name: str, module_name: str) -> Optional[Dict]:
        """从模块中提取中间件信息"""
        # 检查是否启用
        if not getattr(module, 'ENABLED', True):
            return None
        
        middleware_info = {
            'module_name': module_name,
            'file_name': file_name,
            'type': None,
            'middleware_obj': None,
            'priority': getattr(module, 'PRIORITY', 999),
            'config': getattr(module, 'CONFIG', {})
        }
        
        # 查找类中间件
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, BaseHTTPMiddleware) and 
                obj != BaseHTTPMiddleware):
                middleware_info['middleware_obj'] = obj
                middleware_info['type'] = 'class'
                return middleware_info
        
        # 查找函数中间件
        for name, obj in inspect.getmembers(module):
            if (inspect.isfunction(obj) and 
                callable(obj) and
                not name.startswith('_')):
                sig = inspect.signature(obj)
                params = list(sig.parameters.keys())
                if len(params) >= 2:  # 接收request和call_next
                    middleware_info['middleware_func'] = obj
                    middleware_info['type'] = 'function'
                    return middleware_info
        
        # 查找模块变量
        if hasattr(module, 'middleware'):
            middleware_obj = getattr(module, 'middleware')
            if inspect.isclass(middleware_obj) and issubclass(middleware_obj, BaseHTTPMiddleware):
                middleware_info['middleware_obj'] = middleware_obj
                middleware_info['type'] = 'class'
            elif inspect.isfunction(middleware_obj):
                middleware_info['middleware_func'] = middleware_obj
                middleware_info['type'] = 'function'
            return middleware_info
        
        return None
    
    def _register_middlewares(self, middleware_list: List[Dict]):
        """批量注册中间件"""
        registered_count = 0
        
        for mw_info in middleware_list:
            try:
                if mw_info['type'] == 'class':
                    # 注册类中间件
                    self.app.add_middleware(mw_info['middleware_obj'])
                    registered_count += 1
                    print(f"    [CLASS] Registering class middleware: {mw_info['module_name']}.{mw_info['file_name']}")
                    
                elif mw_info['type'] == 'function':
                    # 注册函数中间件
                    self._register_function_middleware(mw_info)
                    registered_count += 1
                    print(f"    [FUNC] Registering function middleware: {mw_info['module_name']}.{mw_info['file_name']}")
                    
            except Exception as e:
                print(f"    [FAIL] Registration failed {mw_info['module_name']}.{mw_info['file_name']}: {e}")
        
        print(f"[DONE] Middleware registration completed: {registered_count} successful, {len(middleware_list)} total")
    
    def _register_function_middleware(self, mw_info: Dict):
        """注册函数中间件"""
        func = mw_info['middleware_func']
        
        class FunctionMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                return await func(request, call_next)
        
        self.app.add_middleware(FunctionMiddleware)

def auto_discover_middleware(app: FastAPI, base_package: List[str] = ["base.core", "base.plugins"]) -> List[Dict]:
    """自动发现中间件（简化入口）"""
    app.add_middleware(CustomCORSMiddleware)
    discoverer = MiddlewareAutoDiscover(app)
    return discoverer.auto_discover_all_modules(base_package)

def register_middlewares(app: FastAPI):
	"""注册中间件（含 base.common 公共层中间件：M8 权限与归属 L1 上下文）"""
	auto_discover_middleware(app, base_package=["base.common", "base.core", "base.plugins"])