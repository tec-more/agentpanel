"""
插件管理器 - 约定式插件系统
插件信息从 manifest.json 读取，路由和模型只在激活状态下加载
插件状态（is_installed, is_enabled）直接存储在各插件的 manifest.json 中

约定式插件结构：
- manifest.json     必需，插件元数据、路由声明和状态
- __init__.py       必需，可以为空文件
- api/              可选，API 路由（在 manifest.json 的 routes 中声明目录）
- models/           可选，数据模型（在 manifest.json 的 models 中声明）
- schemas/          可选，Pydantic Schema（在 manifest.json 的 schemas 中声明，用于文档）
- services/         可选，业务逻辑

manifest.json 示例（路径契约见 base/common/plugin_contract.py）：
{
    "name": "hello_world",
    "display_name": "Hello World",
    "version": "1.0.0",
    "route_prefix": "/v1/hello_world",     // 必填，应用内部前缀，必须以 /v1/ 开头
    "routes": ["api/v1"],                  // 路由目录（递归加载该目录下所有 .py 文件）
    "menus": [],
    "permissions": [],
    "models": ["greeting"],
    "schemas": ["greeting"],
    "is_installed": false,
    "is_enabled": false
}

路由加载规则：
- 浏览器侧统一前缀 /api 由 base/app_wrapper.py 剥离；插件内**禁止**再声明 /api
- routes 指定路由目录（如 "api/v1"），不能指向单个 .py 文件
- route_prefix 必须以 /v1/ 开头；内部接口另用 internal_routes 声明，不带插件业务前缀
- 路由文件导出 {文件名}_router（文件名以 _router 结尾时直接导出同名变量），或 router
- 最终路径 = route_prefix + 路由文件内的路径
  例如: "/v1/hello_world" + "/auth" + "/send-code" = "/v1/hello_world/auth/send-code"
  浏览器请求: /api/v1/hello_world/auth/send-code
- 每个路由文件必须有标准导出；目录不存在、零路由、前缀非法均拒绝装配

注意：
- routes 和 models 会自动加载到应用中
- schemas 不会自动加载，需要在代码中按需 import 使用
  例如: from base.plugins.hello_world.schemas.greeting import GreetingSchema

__init__.py 可选导出（均为可选）：
- router: APIRouter           插件路由（优先于 manifest routes）
- on_enable(app) -> bool      启用时调用
- on_disable() -> bool        禁用时调用
- on_startup() -> None        应用启动时调用
- on_shutdown() -> None       应用关闭时调用
"""
import json
import shutil
import zipfile
import importlib
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, APIRouter

from base.common.log import log
from base.common.setting import settings
from base.common import plugin_contract, plugin_gate


class PluginInstance:
    """插件实例包装器"""

    def __init__(
        self,
        name: str,
        module: Any,
        manifest: dict,
        router: Optional[APIRouter] = None,
        internal_router: Optional[APIRouter] = None,
    ):
        self.name = name
        self.module = module
        self.display_name = manifest.get("display_name", name)
        self.version = manifest.get("version", "0.0.0")
        self.description = manifest.get("description", "")
        self.author = manifest.get("author", "")
        self.website = manifest.get("website", "")
        self.dependencies = manifest.get("dependencies", [])
        self.enabled = False
        # 优先使用模块导出的 router，否则使用 manifest 声明装配出的 router
        self.router: Optional[APIRouter] = getattr(module, 'router', None) or router
        # internal_routes 声明的内部接口，不带插件业务前缀
        self.internal_router: Optional[APIRouter] = internal_router
        # manifest.events.subscribe 声明的订阅（由事件中心统一装卸）
        self.declared_subscriptions: list = (manifest.get("events") or {}).get("subscribe") or []

    async def on_enable(self, app: FastAPI) -> bool:
        """调用插件的 on_enable 钩子（仅显式 False 视为失败）。

        历史问题：部分插件钩子省略 return（如 agent / crm），
        旧的 `if not result` 会把 None 当成失败，导致启用/禁用被误拒。
        """
        if hasattr(self.module, 'on_enable'):
            result = await self.module.on_enable(app)
            if result is False:
                return False
        self.enabled = True
        return True

    async def on_disable(self) -> bool:
        """调用插件的 on_disable 钩子（仅显式 False 视为失败）。"""
        if hasattr(self.module, 'on_disable'):
            result = await self.module.on_disable()
            if result is False:
                return False
        self.enabled = False
        return True

    async def on_startup(self) -> None:
        """调用插件的 on_startup 钩子"""
        if hasattr(self.module, 'on_startup'):
            await self.module.on_startup()

    async def on_shutdown(self) -> None:
        """调用插件的 on_shutdown 钩子"""
        if hasattr(self.module, 'on_shutdown'):
            await self.module.on_shutdown()

    async def on_uninstall(self) -> bool:
        """调用插件的 on_uninstall 钩子"""
        if hasattr(self.module, 'on_uninstall'):
            return await self.module.on_uninstall()
        return True


class PluginManager:
    """插件管理器(单例)"""

    _instance: Optional["PluginManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._plugins: Dict[str, PluginInstance] = {}  # 已加载的插件实例
        self._manifests: Dict[str, dict] = {}  # 插件 manifest 信息缓存
        self._app: Optional[FastAPI] = None
        self._plugins_dir = settings.base_path / "base" / "plugins"
        self._initialized = True

    @property
    def plugins_dir(self) -> Path:
        return self._plugins_dir

    def set_app(self, app: FastAPI) -> None:
        self._app = app

    def get_plugin(self, name: str) -> Optional[PluginInstance]:
        return self._plugins.get(name)

    def get_active_plugin(self, name: str) -> Optional[PluginInstance]:
        """返回「已加载 且 已启用 且 manifest 双真」的插件，供后台作业门控使用。"""
        plugin = self._plugins.get(name)
        if plugin and plugin.enabled and plugin_gate.is_plugin_active(name):
            return plugin
        return None

    def get_all_plugins(self) -> Dict[str, PluginInstance]:
        return self._plugins.copy()

    # ==================== Manifest 管理 ====================

    def get_manifest(self, name: str) -> Optional[dict]:
        """获取插件 manifest 信息"""
        if name in self._manifests:
            return self._manifests[name]
        return self._read_manifest(name)

    def _read_manifest(self, name: str) -> Optional[dict]:
        """从 manifest.json 读取插件信息"""
        plugin_dir = self._plugins_dir / name
        manifest_file = plugin_dir / "manifest.json"

        if not manifest_file.exists():
            return None

        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                self._manifests[name] = manifest
                return manifest
        except Exception as e:
            log.error(f"读取插件 {name} 的 manifest.json 失败: {e}")
            return None

    def _write_manifest(self, name: str, manifest: dict) -> bool:
        """写入 manifest.json"""
        plugin_dir = self._plugins_dir / name
        manifest_file = plugin_dir / "manifest.json"

        try:
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=4)
            self._manifests[name] = manifest
            return True
        except Exception as e:
            log.error(f"写入插件 {name} 的 manifest.json 失败: {e}")
            return False

    def update_plugin_status(self, name: str, is_installed: bool = None, is_enabled: bool = None) -> bool:
        """更新插件状态（写入 manifest.json）"""
        manifest = self.get_manifest(name)
        if not manifest:
            return False

        if is_installed is not None:
            manifest["is_installed"] = is_installed
        if is_enabled is not None:
            manifest["is_enabled"] = is_enabled

        written = self._write_manifest(name, manifest)
        plugin_gate.invalidate(name)
        return written

    def get_enabled_plugins_from_manifests(self) -> List[str]:
        """获取已安装且激活的插件列表（统一走 plugin_gate 判定）。"""
        return [name for name in self.discover_plugins() if plugin_gate.is_plugin_active(name)]

    def discover_plugins(self) -> List[str]:
        """发现插件目录中的所有插件（通过 manifest.json）"""
        discovered = []
        exclude_dirs = {"__pycache__", ".git"}

        if not self._plugins_dir.exists():
            return discovered

        for item in self._plugins_dir.iterdir():
            if item.is_dir() and not item.name.startswith("_") and item.name not in exclude_dirs:
                manifest_file = item / "manifest.json"
                if manifest_file.exists():
                    discovered.append(item.name)

        return discovered

    def discover_plugins_info(self) -> List[dict]:
        """发现所有插件并返回 manifest 信息"""
        discovered = self.discover_plugins()
        result = []

        for name in discovered:
            manifest = self.get_manifest(name)
            if manifest:
                result.append({
                    "name": manifest.get("name", name),
                    "display_name": manifest.get("display_name", name),
                    "version": manifest.get("version", "1.0.0"),
                    "description": manifest.get("description", ""),
                    "author": manifest.get("author", ""),
                    "website": manifest.get("website", ""),
                    "dependencies": manifest.get("dependencies", []),
                    "is_installed": manifest.get("is_installed", False),
                    "is_enabled": manifest.get("is_enabled", False),
                })

        return result

    def load_plugin(self, name: str) -> Optional[PluginInstance]:
        """加载指定插件模块"""
        if name in self._plugins:
            return self._plugins[name]

        plugin_dir = self._plugins_dir / name
        init_file = plugin_dir / "__init__.py"
        manifest_file = plugin_dir / "manifest.json"

        if not manifest_file.exists():
            log.error(f"插件 manifest 不存在: {manifest_file}")
            return None

        if not init_file.exists():
            log.error(f"插件入口文件不存在: {init_file}")
            return None

        try:
            # 声明契约校验：缺字段/前缀非法/目录不存在一律拒绝装配
            manifest = self.get_manifest(name)
            problems = plugin_contract.validate_manifest(name, manifest or {}, plugin_dir)
            if problems:
                raise plugin_contract.ContractViolation(name, problems)

            # 动态加载插件模块
            spec = importlib.util.spec_from_file_location(
                f"base.plugins.{name}", init_file
            )
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # manifest 是装配唯一输入：始终按声明加载，零路由直接拒绝
            router = self._load_routes_from_manifest(name, manifest)
            internal_router = self._load_internal_routes_from_manifest(name, manifest)

            # 插件入口自行导出 router 属声明外注册，记录一致性偏差
            if hasattr(module, 'router'):
                log.warning(
                    f"插件 {name} 在 __init__.py 导出了 router，覆盖 manifest 声明；"
                    f"请在 manifest.routes 中统一声明（AC-PLR-01-2）"
                )
                router = getattr(module, 'router') or router

            # 注意: schemas 不需要自动加载，由开发者在使用时按需 import

            plugin_instance = PluginInstance(name, module, manifest, router, internal_router)
            self._plugins[name] = plugin_instance
            log.info(f"插件加载成功: {name}")
            return plugin_instance

        except plugin_contract.ContractViolation as e:
            log.error(str(e))
            return None
        except Exception as e:
            log.error(f"加载插件 {name} 失败: {e}")
            return None

    def _load_routes_from_manifest(self, name: str, manifest: dict) -> Optional[APIRouter]:
        """按 manifest.routes 装配路由（声明为唯一输入）。

        - route_prefix 必须以 /v1/ 开头，且不得再写浏览器侧 /api
        - 目录不存在、内部前缀含 /api、零路由均拒绝装配（AC-PLR-01-1/01-2）
        """
        plugin_dir = self._plugins_dir / name

        routes_config = manifest.get("routes", [])
        if not routes_config:
            return None

        route_prefix = manifest.get("route_prefix", "")
        problems = plugin_contract.validate_route_prefix(route_prefix)
        combined_router = APIRouter(prefix=route_prefix) if route_prefix else APIRouter()
        loaded_count = 0

        # 遍历 routes 配置中的每个路径
        for route_path in routes_config:
            route_dir = plugin_dir / route_path

            # 检查目录是否存在：声明的目录缺失属于契约违约，不再静默跳过
            if not route_dir.is_dir():
                problems.append(f"routes 声明的目录不存在: {route_path}")
                continue

            # 递归遍历该目录下的所有 .py 文件（排除 __init__.py）
            # 先收集所有文件，然后按文件名排序：以 _router 结尾的文件优先加载
            route_files = []
            for route_file in route_dir.rglob("*.py"):
                if route_file.name == "__init__.py":
                    continue
                route_files.append(route_file)
            
            # 排序：以 _router 结尾的文件优先加载
            route_files.sort(key=lambda f: 0 if f.stem.endswith("_router") else 1)
            
            for route_file in route_files:

                try:
                    # 计算相对路径和模块路径
                    relative_path = route_file.relative_to(plugin_dir)
                    module_path = f"base.plugins.{name}.{relative_path.as_posix().replace('/', '.')[:-3]}"  # 去掉.py

                    candidates = plugin_contract.router_attr_candidates(route_file)

                    # 动态加载模块
                    spec = importlib.util.spec_from_file_location(module_path, route_file)
                    if spec and spec.loader:
                        route_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(route_module)

                        router_attr = next(
                            (attr for attr in candidates if hasattr(route_module, attr)), None
                        )
                        if not router_attr:
                            log.warning(
                                f"插件 {name} 路由文件 {relative_path} 未导出标准变量 "
                                f"{candidates[0]}（或 router），已跳过"
                            )
                            continue
                        router_obj = getattr(route_module, router_attr)
                        if not isinstance(router_obj, APIRouter):
                            log.warning(f"插件 {name} 的 {relative_path}:{router_attr} 不是 APIRouter")
                            continue
                        inner_problems = plugin_contract.validate_no_browser_prefix(
                            getattr(router_obj, "prefix", "") or ""
                        )
                        if inner_problems:
                            problems.extend(f"{relative_path}: {p}" for p in inner_problems)
                            continue
                        combined_router.include_router(router_obj)
                        loaded_count += 1
                        log.debug(f"已加载路由文件: {relative_path} -> {router_attr}")
                except Exception as e:
                    # 单个文件导入失败属于一致性偏差，记录但不阻断整个插件装配
                    log.error(f"加载路由文件 {route_file} 失败: {e}")

        if loaded_count == 0:
            problems.append("routes 声明的目录未加载出任何 APIRouter（零路由，启用必失败）")
        if problems:
            raise plugin_contract.ContractViolation(name, problems)
        prefix_info = f" (prefix: {route_prefix})" if route_prefix else ""
        log.info(f"插件 {name} 共加载了 {loaded_count} 个路由文件{prefix_info}")
        return combined_router

    def _load_internal_routes_from_manifest(self, name: str, manifest: dict) -> Optional[APIRouter]:
        """装配 internal_routes 声明的内部接口。

        这类接口自带 /internal/... 前缀，不套插件业务前缀，
        也不在浏览器侧 /api 命名空间内（由 app_wrapper 白名单放行）。
        """
        configs = manifest.get("internal_routes") or []
        if not configs:
            return None

        plugin_dir = self._plugins_dir / name
        combined = APIRouter()
        loaded_count = 0
        problems: list[str] = []

        for route_path in configs:
            route_dir = plugin_dir / route_path
            if not route_dir.is_dir():
                problems.append(f"internal_routes 声明的目录不存在: {route_path}")
                continue
            for route_file in sorted(route_dir.rglob("*.py")):
                if route_file.name == "__init__.py":
                    continue
                relative_path = route_file.relative_to(plugin_dir)
                module_path = (
                    f"base.plugins.{name}."
                    f"{relative_path.as_posix().replace('/', '.')[:-3]}"
                )
                try:
                    spec = importlib.util.spec_from_file_location(module_path, route_file)
                    if not (spec and spec.loader):
                        continue
                    route_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(route_module)
                    candidates = plugin_contract.router_attr_candidates(route_file)
                    router_attr = next(
                        (attr for attr in candidates if hasattr(route_module, attr)), None
                    )
                    if not router_attr:
                        continue
                    router_obj = getattr(route_module, router_attr)
                    if isinstance(router_obj, APIRouter):
                        combined.include_router(router_obj)
                        loaded_count += 1
                except Exception as e:
                    log.error(f"加载内部路由 {route_file} 失败: {e}")

        if loaded_count == 0:
            problems.append("internal_routes 未加载出任何 APIRouter")
        if problems:
            raise plugin_contract.ContractViolation(name, problems)
        log.info(f"插件 {name} 共加载了 {loaded_count} 个内部路由文件")
        return combined

    async def _process_plugin_menus(self, name: str, manifest: dict) -> bool:
        """处理插件的菜单配置"""
        try:
            from base.core.users.services.menu_service import MenuService
            from base.core.users.schemas.rbac import MenuCreate, MenuUpdate
            
            # 获取菜单配置
            menus_config = manifest.get("menus", [])
            if not menus_config:
                return True
            
            # 递归处理菜单（创建或更新）
            async def process_menu_recursive(menu_config, parent_id=None):
                # 查找菜单
                existing_menu = await MenuService.get_menu_by_name_and_path(
                    menu_config["name"],
                    menu_config["path"]
                )
                
                if existing_menu:
                    # 检查菜单是否真的发生了变化
                    # 注意：配置中用 is_hidden，数据库模型中用 is_visible，需要转换
                    config_is_visible = not menu_config.get("is_hidden", False)
                    
                    # 调试：打印每个字段的比较结果
                    changes_detail = []
                    if existing_menu.name != menu_config["name"]:
                        changes_detail.append(f"name: {existing_menu.name} != {menu_config['name']}")
                    if existing_menu.path != menu_config["path"]:
                        changes_detail.append(f"path: {existing_menu.path} != {menu_config['path']}")
                    # 处理空字符串和 None 的情况（两者视为相等）
                    db_icon = existing_menu.icon if existing_menu.icon else None
                    config_icon = menu_config.get("icon") if menu_config.get("icon") else None
                    if db_icon != config_icon:
                        changes_detail.append(f"icon: {existing_menu.icon} != {config_icon}")
                    # 处理 component 的空字符串和 None 的情况
                    db_component = existing_menu.component if existing_menu.component else None
                    config_component = menu_config.get("component") if menu_config.get("component") else None
                    if db_component != config_component:
                        changes_detail.append(f"component: {existing_menu.component} != {config_component}")
                    if existing_menu.parent_id != parent_id:
                        changes_detail.append(f"parent_id: {existing_menu.parent_id} != {parent_id}")
                    if existing_menu.is_visible != config_is_visible:
                        changes_detail.append(f"is_visible: {existing_menu.is_visible} != {config_is_visible}")
                    if existing_menu.menu_type != menu_config.get("menu_type", "menu"):
                        changes_detail.append(f"menu_type: {existing_menu.menu_type} != {menu_config.get('menu_type', 'menu')}")
                    # 处理 permission 的空字符串和 None 的情况
                    db_permission = existing_menu.permission if existing_menu.permission else None
                    config_permission = menu_config.get("permission_code") if menu_config.get("permission_code") else None
                    if db_permission != config_permission:
                        changes_detail.append(f"permission: {existing_menu.permission} != {config_permission}")
                    if not existing_menu.is_active:
                        changes_detail.append(f"is_active: {existing_menu.is_active} != True")
                    
                    has_changes = len(changes_detail) > 0
                    
                    if has_changes:
                        log.debug(f"菜单 {menu_config['name']} ({menu_config['path']}) 发生变化: {', '.join(changes_detail)}")
                    
                    if has_changes:
                        # 只有在真正变化时才更新菜单 - 保留现有 sort 值
                        update_data = MenuUpdate(
                            name=menu_config["name"],
                            path=menu_config["path"],
                            icon=menu_config.get("icon"),
                            component=menu_config.get("component"),
                            parent_id=parent_id,
                            sort=existing_menu.sort,  # 保留数据库中的排序值，不覆盖
                            is_hidden=menu_config.get("is_hidden", False),
                            menu_type=menu_config.get("menu_type", "menu"),
                            permission_code=menu_config.get("permission_code"),
                            is_active=True
                        )
                        menu = await MenuService.update_menu(existing_menu.id, update_data)
                        log.debug(f"更新菜单: {menu_config['name']} ({menu_config['path']}) - 保留排序值: {existing_menu.sort}")
                    else:
                        log.debug(f"菜单未变化，跳过更新: {menu_config['name']} ({menu_config['path']})")
                        menu = existing_menu
                else:
                    # 创建菜单 - 使用配置中的 sort 值
                    create_data = MenuCreate(
                        name=menu_config["name"],
                        path=menu_config["path"],
                        icon=menu_config.get("icon"),
                        component=menu_config.get("component"),
                        parent_id=parent_id,
                        sort=menu_config.get("sort", 0),
                        is_hidden=menu_config.get("is_hidden", False),
                        menu_type=menu_config.get("menu_type", "menu"),
                        permission_code=menu_config.get("permission_code")
                    )
                    menu = await MenuService.create_menu(create_data)
                    log.debug(f"创建菜单: {menu_config['name']} ({menu_config['path']}) - 初始排序值: {menu_config.get('sort', 0)}")
                
                # 处理子菜单
                for child_config in menu_config.get("children", []):
                    await process_menu_recursive(child_config, menu.id)
            
            # 处理所有顶级菜单
            for menu_config in menus_config:
                await process_menu_recursive(menu_config)
            
            log.info(f"插件 {name} 的菜单配置已处理完成")
            return True
            
        except Exception as e:
            log.error(f"处理插件 {name} 的菜单配置失败: {e}")
            return False

    async def _process_plugin_permissions(self, name: str, manifest: dict) -> bool:
        """处理插件的权限配置"""
        try:
            from base.core.users.services.rbac_service import PermissionService
            from base.core.users.schemas.rbac import PermissionCreate, PermissionUpdate

            permissions_config = manifest.get("permissions", [])
            if not permissions_config:
                return True

            for perm_config in permissions_config:
                code = perm_config.get("code")
                if not code:
                    continue

                existing_perm = await PermissionService.get_by_code(code)

                if existing_perm:
                    has_changes = False
                    if existing_perm.name != perm_config.get("name"):
                        has_changes = True
                    if existing_perm.description != perm_config.get("description"):
                        has_changes = True
                    if existing_perm.module != perm_config.get("module"):
                        has_changes = True
                    if not existing_perm.is_active:
                        has_changes = True

                    if has_changes:
                        update_data = PermissionUpdate(
                            name=perm_config.get("name"),
                            description=perm_config.get("description"),
                            module=perm_config.get("module"),
                            is_active=True
                        )
                        await PermissionService.update_permission(existing_perm.id, update_data)
                        log.debug(f"更新权限: {code}")
                else:
                    create_data = PermissionCreate(
                        name=perm_config.get("name"),
                        code=code,
                        description=perm_config.get("description"),
                        module=perm_config.get("module")
                    )
                    await PermissionService.create_permission(create_data)
                    log.debug(f"创建权限: {code}")

            log.info(f"插件 {name} 的权限配置已处理完成")
            return True

        except Exception as e:
            log.error(f"处理插件 {name} 的权限配置失败: {e}")
            return False

    async def enable_plugin(self, name: str) -> bool:
        """启用插件"""
        manifest = self.get_manifest(name)
        if not manifest:
            log.error(f"插件 {name} 的 manifest.json 不存在")
            return False

        # 加载插件
        plugin = self._plugins.get(name)
        if not plugin:
            plugin = self.load_plugin(name)
            if not plugin:
                return False

        if plugin.enabled:
            return True

        if not self._app:
            log.error("FastAPI 应用未初始化")
            return False

        try:
            # 检查依赖
            dependencies = manifest.get("dependencies", [])
            for dep in dependencies:
                dep_plugin = self._plugins.get(dep)
                if not dep_plugin or not dep_plugin.enabled:
                    log.error(f"插件 {name} 依赖的插件 {dep} 未启用")
                    return False

            # 调用启用钩子
            success = await plugin.on_enable(self._app)
            if not success:
                return False

            # 处理菜单配置
            await self._process_plugin_menus(name, manifest)

            # 处理权限配置
            await self._process_plugin_permissions(name, manifest)

            # 注册 manifest 声明的业务路由与内部路由（唯一装配入口）
            if plugin.router:
                self._app.include_router(plugin.router)
                log.info(f"已注册插件路由: {name}")
            if plugin.internal_router:
                self._app.include_router(plugin.internal_router)
                log.info(f"已注册插件内部路由: {name}")

            # 声明订阅统一由事件中心激活：运行时启用即时生效，不再依赖 on_startup
            await self._sync_plugin_subscriptions(name, manifest, active=True)

            # 更新 manifest 状态（同时使门控缓存失效）
            self.update_plugin_status(name, is_installed=True, is_enabled=True)

            log.info(f"插件已启用: {manifest.get('display_name', name)}")
            return True

        except Exception as e:
            log.error(f"启用插件 {name} 失败: {e}")
            return False

    async def _cleanup_plugin_menus(self, name: str, manifest: dict) -> bool:
        """清理插件的菜单配置"""
        try:
            from base.core.users.services.menu_service import MenuService
            
            # 获取菜单配置
            menus_config = manifest.get("menus", [])
            if not menus_config:
                return True
            
            # 递归删除菜单
            async def delete_menu_recursive(menu_config):
                # 查找菜单
                from base.core.users.models.rbac import Menu
                menu = await Menu.filter(
                    name=menu_config["name"],
                    path=menu_config["path"]
                ).first()
                
                if menu:
                    # 先删除子菜单
                    for child_config in menu_config.get("children", []):
                        await delete_menu_recursive(child_config)
                    
                    # 删除当前菜单
                    await MenuService.delete_menu(menu.id)
            
            # 处理所有顶级菜单
            for menu_config in menus_config:
                await delete_menu_recursive(menu_config)
            
            log.info(f"插件 {name} 的菜单配置已清理完成")
            return True
            
        except Exception as e:
            log.error(f"清理插件 {name} 的菜单配置失败: {e}")
            return False

    async def _cleanup_plugin_permissions(self, name: str, manifest: dict) -> bool:
        """禁用时清理插件声明的权限，避免孤儿记录（AC-PLR-03-2）。"""
        try:
            from base.core.users.models.rbac import Permission

            codes: list[str] = []

            def collect(items):
                for item in items or []:
                    if not isinstance(item, dict):
                        continue
                    code = item.get("code") or item.get("permission_code")
                    if code:
                        codes.append(code)
                    collect(item.get("children"))

            collect(manifest.get("permissions", []))
            if not codes:
                return True
            try:
                await Permission.filter(code__in=codes).delete()
            except Exception:
                # 已被角色引用时退化为停用，避免破坏既有授权
                await Permission.filter(code__in=codes).update(is_active=False)
            log.info(f"插件 {name} 的权限配置已清理: {len(codes)} 条")
            return True
        except Exception as e:
            log.error(f"清理插件 {name} 的权限配置失败: {e}")
            return False

    async def _sync_plugin_subscriptions(self, name: str, manifest: dict, active: bool) -> None:
        """把 manifest.events.subscribe 交给事件中心统一装卸。

        事件中心尚未初始化时静默跳过（模块通过延迟导入，保证装配器可独立运行）。
        """
        try:
            from base.core.events.registry import event_center
        except ImportError:
            return
        try:
            await event_center.sync_plugin(name, manifest, active=active)
        except Exception as e:
            log.error(f"插件 {name} 订阅同步失败(active={active}): {e}")

    async def disable_plugin(self, name: str) -> bool:
        """禁用插件"""
        plugin = self._plugins.get(name)
        if not plugin or not plugin.enabled:
            self.update_plugin_status(name, is_enabled=False)
            return True

        try:
            # 检查依赖
            for other_name, other_plugin in self._plugins.items():
                if other_plugin.enabled:
                    other_manifest = self.get_manifest(other_name)
                    if other_manifest and name in other_manifest.get("dependencies", []):
                        log.error(f"无法禁用插件 {name}，插件 {other_name} 依赖它")
                        return False

            success = await plugin.on_disable()
            if not success:
                return False

            # 与启用对称：清理菜单 + 权限，注销声明订阅
            manifest = self.get_manifest(name)
            if manifest:
                await self._cleanup_plugin_menus(name, manifest)
                await self._cleanup_plugin_permissions(name, manifest)
            await self._sync_plugin_subscriptions(name, manifest or {}, active=False)

            self.update_plugin_status(name, is_enabled=False)

            log.info(f"插件已禁用: {manifest.get('display_name', name) if manifest else name}")
            return True

        except Exception as e:
            log.error(f"禁用插件 {name} 失败: {e}")
            return False

    async def install_plugin(self, plugin_path: str) -> Optional[str]:
        """安装插件(从 zip 文件或目录)"""
        try:
            source_path = Path(plugin_path)

            if source_path.suffix == ".zip":
                return await self._install_from_zip(source_path)
            elif source_path.is_dir():
                return await self._install_from_dir(source_path)
            else:
                log.error(f"不支持的插件格式: {plugin_path}")
                return None

        except Exception as e:
            log.error(f"安装插件失败: {e}")
            return None

    async def _install_from_zip(self, zip_path: Path) -> Optional[str]:
        """从 zip 文件安装插件"""
        if not zip_path.exists():
            return None

        temp_dir = self._plugins_dir / "_temp_install"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(temp_dir)

            items = list(temp_dir.iterdir())
            plugin_dir = items[0] if len(items) == 1 and items[0].is_dir() else temp_dir

            manifest_file = plugin_dir / "manifest.json"
            if not manifest_file.exists():
                log.error("无效的插件结构：缺少 manifest.json")
                return None

            if not (plugin_dir / "__init__.py").exists():
                log.error("无效的插件结构：缺少 __init__.py")
                return None

            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                plugin_name = manifest.get("name", plugin_dir.name)

            target_dir = self._plugins_dir / plugin_name
            if target_dir.exists():
                shutil.rmtree(target_dir)

            shutil.move(str(plugin_dir), str(target_dir))
            self.update_plugin_status(plugin_name, is_installed=True, is_enabled=False)

            log.info(f"插件安装成功: {plugin_name}")
            return plugin_name

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    async def _install_from_dir(self, source_dir: Path) -> Optional[str]:
        """从目录安装插件"""
        manifest_file = source_dir / "manifest.json"
        if not manifest_file.exists():
            log.error("无效的插件结构：缺少 manifest.json")
            return None

        if not (source_dir / "__init__.py").exists():
            log.error("无效的插件结构：缺少 __init__.py")
            return None

        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            plugin_name = manifest.get("name", source_dir.name)

        target_dir = self._plugins_dir / plugin_name

        if target_dir.exists():
            shutil.rmtree(target_dir)

        shutil.copytree(source_dir, target_dir)
        self.update_plugin_status(plugin_name, is_installed=True, is_enabled=False)

        log.info(f"插件安装成功: {plugin_name}")
        return plugin_name

    async def uninstall_plugin(self, name: str) -> bool:
        """卸载插件"""
        plugin = self._plugins.get(name)

        try:
            if plugin and plugin.enabled:
                await self.disable_plugin(name)

            if plugin:
                await plugin.on_uninstall()

            if name in self._plugins:
                del self._plugins[name]

            if name in self._manifests:
                del self._manifests[name]

            plugin_dir = self._plugins_dir / name
            if plugin_dir.exists():
                shutil.rmtree(plugin_dir)

            log.info(f"插件已卸载: {name}")
            return True

        except Exception as e:
            log.error(f"卸载插件 {name} 失败: {e}")
            return False

    async def load_enabled_plugins(self) -> None:
        """加载并启用已激活的插件（处理依赖关系）"""
        # 获取所有已启用的插件
        enabled_plugins = self.get_enabled_plugins_from_manifests()
        
        # 同步数据库状态（如果可用）
        try:
            from base.core.extension.models.plugin import Plugin as PluginModel
            db_enabled_plugins = await PluginModel.filter(is_enabled=True, is_installed=True).all()
            for plugin_record in db_enabled_plugins:
                if plugin_record.name not in enabled_plugins:
                    enabled_plugins.append(plugin_record.name)
        except Exception as e:
            log.debug(f"数据库插件状态同步跳过: {e}")
        
        # 构建插件依赖图
        plugin_deps = {}
        all_manifests = {}
        for plugin_name in enabled_plugins:
            manifest = self.get_manifest(plugin_name)
            if manifest:
                all_manifests[plugin_name] = manifest
                dependencies = manifest.get("dependencies", [])
                # 过滤出存在且已启用的依赖
                filtered_deps = []
                for dep in dependencies:
                    dep_manifest = self.get_manifest(dep)
                    if dep_manifest and (dep_manifest.get("is_installed") and dep_manifest.get("is_enabled")):
                        filtered_deps.append(dep)
                plugin_deps[plugin_name] = filtered_deps
        
        # 拓扑排序
        visited = set()
        temp_visited = set()
        order = []
        cycle_found = False
        
        def dfs(plugin):
            nonlocal cycle_found
            if cycle_found:
                return
            
            if plugin in temp_visited:
                log.error(f"插件依赖循环: {plugin}")
                cycle_found = True
                return
            
            if plugin in visited:
                return
            
            temp_visited.add(plugin)
            
            for dep in plugin_deps.get(plugin, []):
                dfs(dep)
            
            temp_visited.remove(plugin)
            visited.add(plugin)
            order.append(plugin)
        
        # 对所有插件执行 DFS
        for plugin_name in plugin_deps.keys():
            if plugin_name not in visited:
                dfs(plugin_name)
        
        if cycle_found:
            log.error("插件依赖存在循环，加载失败")
            return
        
        # 按拓扑排序顺序启用插件（启用时会自动处理菜单）
        log.debug(f"插件拓扑排序结果: {order}")
        for plugin_name in order:
            await self.enable_plugin(plugin_name)
        
        log.info("插件加载完成")

    async def startup(self) -> None:
        """应用启动时调用"""
        for plugin in self._plugins.values():
            if plugin.enabled:
                await plugin.on_startup()

    async def shutdown(self) -> None:
        """应用关闭时调用"""
        for plugin in self._plugins.values():
            if plugin.enabled:
                await plugin.on_shutdown()


# 显式注册：进程启动时由 base.start 调用 init_plugin_manager() 创建实例，
# 其他模块通过 get_plugin_manager() 获取；导入本模块不再产生隐式单例。
_plugin_manager: Optional[PluginManager] = None


def init_plugin_manager() -> PluginManager:
    """创建（或返回已创建的）插件管理器实例（幂等）。"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def get_plugin_manager() -> PluginManager:
    """获取已初始化的插件管理器；未初始化时 fail-fast。"""
    if _plugin_manager is None:
        raise RuntimeError(
            "插件管理器未初始化：进程启动需先调用 init_plugin_manager()"
        )
    return _plugin_manager
