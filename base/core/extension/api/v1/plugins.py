"""
插件管理 API
"""
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, status, Query, UploadFile, File

from base.core.extension.services.plugin_service import PluginService
from base.core.extension.schemas.plugin import PluginSettingsUpdate, PluginUpdate, PluginUninstallRequest
from base.common.security import get_current_user_id, verify_password
from base.common.response import SuccessResponse, ErrorResponse
from base.core.users.services.user_service import UserService
from base.plugins import plugin_manager

router = APIRouter(prefix="/v1/plugins", tags=["插件管理"])


async def check_admin(current_user_id: int) -> bool:
    """检查管理员权限"""
    user = await UserService.get_by_id(current_user_id)
    return user and user.is_superuser


@router.get("/list", summary="获取插件列表")
async def get_plugin_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=200, description="每页数量"),
    is_enabled: Optional[bool] = Query(None, description="是否启用"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    current_user_id: int = Depends(get_current_user_id),
):
    """获取已安装的插件列表(分页)"""
    if not await check_admin(current_user_id):
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    plugins, total = await PluginService.get_plugin_list(
        page=page,
        page_size=page_size,
        is_enabled=is_enabled,
        keyword=keyword,
    )

    items = [await p.to_dict() for p in plugins]

    return SuccessResponse(data={
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    })


@router.get("/discover", summary="发现可用插件")
async def discover_plugins(
    current_user_id: int = Depends(get_current_user_id),
):
    """发现插件目录中的所有可用插件（从 manifest.json 读取，不加载模块）"""
    if not await check_admin(current_user_id):
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    # 使用 discover_plugins_info 直接从 manifest.json 读取信息，避免加载插件模块
    discovered = plugin_manager.discover_plugins_info()
    result = []

    for info in discovered:
        db_record = await PluginService.get_by_name(info["name"])
        result.append({
            "name": info["name"],
            "display_name": info["display_name"],
            "version": info["version"],
            "description": info.get("description", ""),
            "author": info.get("author", ""),
            "is_installed": db_record is not None,
            "is_enabled": db_record.is_enabled if db_record else False,
        })

    return SuccessResponse(data=result)


@router.post("/sync", summary="同步插件")
async def sync_plugins(
    current_user_id: int = Depends(get_current_user_id),
):
    """同步插件目录中的插件到数据库（从 manifest.json 读取，不加载模块）"""
    if not await check_admin(current_user_id):
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    # 使用 discover_plugins_info 直接从 manifest.json 读取信息，避免加载插件模块
    discovered = plugin_manager.discover_plugins_info()
    synced = []

    for info in discovered:
        db_plugin = await PluginService.sync_plugin(
            name=info["name"],
            display_name=info["display_name"],
            version=info["version"],
            description=info.get("description"),
            author=info.get("author"),
            website=info.get("website"),
            dependencies=info.get("dependencies", []),
            is_installed=info.get("is_installed", False),
            is_enabled=info.get("is_enabled", False),
        )
        synced.append(await db_plugin.to_dict())

    return SuccessResponse(data=synced, msg=f"同步成功，共处理 {len(synced)} 个插件")


@router.get("/{plugin_id}", summary="获取插件详情")
async def get_plugin_detail(
    plugin_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    """获取插件详细信息"""
    if not await check_admin(current_user_id):
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    plugin = await PluginService.get_by_id(plugin_id)
    if not plugin:
        return ErrorResponse(msg="插件不存在", status_code=status.HTTP_404_NOT_FOUND)

    return SuccessResponse(data=await plugin.to_dict())


@router.post("/{plugin_id}/enable", summary="启用插件")
async def enable_plugin(
    plugin_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    """启用指定插件"""
    if not await check_admin(current_user_id):
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    plugin = await PluginService.get_by_id(plugin_id)
    if not plugin:
        return ErrorResponse(msg="插件不存在", status_code=status.HTTP_404_NOT_FOUND)

    # 调用插件管理器启用插件
    success = await plugin_manager.enable_plugin(plugin.name)
    if not success:
        return ErrorResponse(msg="启用插件失败", status_code=status.HTTP_400_BAD_REQUEST)

    # 更新数据库状态
    plugin = await PluginService.enable_plugin(plugin_id)

    return SuccessResponse(data=await plugin.to_dict(), msg="插件已启用")


@router.post("/{plugin_id}/disable", summary="禁用插件")
async def disable_plugin(
    plugin_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    """禁用指定插件"""
    if not await check_admin(current_user_id):
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    plugin = await PluginService.get_by_id(plugin_id)
    if not plugin:
        return ErrorResponse(msg="插件不存在", status_code=status.HTTP_404_NOT_FOUND)

    # 调用插件管理器禁用插件
    success = await plugin_manager.disable_plugin(plugin.name)
    if not success:
        return ErrorResponse(msg="禁用插件失败", status_code=status.HTTP_400_BAD_REQUEST)

    # 更新数据库状态
    plugin = await PluginService.disable_plugin(plugin_id)

    return SuccessResponse(data=await plugin.to_dict(), msg="插件已禁用")


@router.post("/{plugin_id}/install", summary="安装插件")
async def install_plugin(
    plugin_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    """安装已同步到插件目录的插件（将安装状态置为已安装，插件文件需已存在）"""
    if not await check_admin(current_user_id):
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    plugin = await PluginService.get_by_id(plugin_id)
    if not plugin:
        return ErrorResponse(msg="插件不存在", status_code=status.HTTP_404_NOT_FOUND)

    if plugin.is_installed:
        return ErrorResponse(msg="插件已安装，无需重复安装", status_code=status.HTTP_400_BAD_REQUEST)

    # 校验插件文件（manifest.json）是否存在
    manifest = plugin_manager.get_manifest(plugin.name)
    if not manifest:
        return ErrorResponse(msg="插件文件缺失，请重新上传插件包", status_code=status.HTTP_400_BAD_REQUEST)

    # 写入 manifest 安装状态（安装后默认不启用，需用户手动启用）
    plugin_manager.update_plugin_status(plugin.name, is_installed=True, is_enabled=False)

    # 更新数据库记录
    plugin = await PluginService.set_install_status(plugin_id, True)

    return SuccessResponse(data=await plugin.to_dict(), msg=f"插件 {plugin.display_name} 安装成功")


@router.post("/{plugin_id}/uninstall", summary="卸载插件（需验证密码）")
async def uninstall_plugin(
    plugin_id: int,
    body: PluginUninstallRequest,
    current_user_id: int = Depends(get_current_user_id),
):
    """卸载指定插件（需管理员权限且验证登录密码）"""
    # 1. 权限校验：仅超级管理员可卸载
    if not await check_admin(current_user_id):
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    plugin = await PluginService.get_by_id(plugin_id)
    if not plugin:
        return ErrorResponse(msg="插件不存在", status_code=status.HTTP_404_NOT_FOUND)

    # 2. 仅已安装插件可卸载
    if not plugin.is_installed:
        return ErrorResponse(msg="插件未安装，无需卸载", status_code=status.HTTP_400_BAD_REQUEST)

    # 3. 验证当前用户登录密码
    user = await UserService.get_by_id(current_user_id)
    if not user or not user.password or not verify_password(body.password, user.password):
        return ErrorResponse(msg="登录密码验证失败，无法卸载插件", status_code=status.HTTP_400_BAD_REQUEST)

    plugin_name = plugin.display_name

    # 4. 若插件处于启用状态，先禁用（卸载路由、菜单等）
    if plugin.is_enabled:
        try:
            await plugin_manager.disable_plugin(plugin.name)
        except Exception:
            pass  # 禁用失败不阻断卸载流程

    # 5. 写入 manifest：未安装 + 未启用（保留插件文件，便于再次安装）
    plugin_manager.update_plugin_status(plugin.name, is_installed=False, is_enabled=False)

    # 6. 更新数据库记录
    plugin = await PluginService.set_install_status(plugin_id, False)

    return SuccessResponse(data=await plugin.to_dict(), msg=f"插件 {plugin_name} 已卸载")


@router.post("/upload", summary="上传并安装插件")
async def upload_plugin(
    file: UploadFile = File(..., description="插件 ZIP 文件"),
    current_user_id: int = Depends(get_current_user_id),
):
    """上传 ZIP 文件安装插件"""
    if not await check_admin(current_user_id):
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    if not file.filename.endswith(".zip"):
        return ErrorResponse(msg="只支持 ZIP 格式的插件包", status_code=status.HTTP_400_BAD_REQUEST)

    temp_dir = Path(tempfile.mkdtemp())
    temp_file = temp_dir / file.filename

    try:
        with open(temp_file, "wb") as f:
            content = await file.read()
            f.write(content)

        # 安装插件
        plugin_name = await plugin_manager.install_plugin(str(temp_file))
        if not plugin_name:
            return ErrorResponse(msg="安装插件失败", status_code=status.HTTP_400_BAD_REQUEST)

        # 从 manifest.json 读取插件信息同步到数据库，不加载模块
        manifest = plugin_manager.get_manifest(plugin_name)
        if manifest:
            db_plugin = await PluginService.sync_plugin(
                name=manifest.get("name", plugin_name),
                display_name=manifest.get("display_name", plugin_name),
                version=manifest.get("version", "1.0.0"),
                description=manifest.get("description"),
                author=manifest.get("author"),
                website=manifest.get("website"),
                dependencies=manifest.get("dependencies", []),
            )
            return SuccessResponse(
                data=await db_plugin.to_dict(),
                msg=f"插件 {manifest.get('display_name', plugin_name)} 安装成功"
            )

        return ErrorResponse(msg="安装插件失败", status_code=status.HTTP_400_BAD_REQUEST)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@router.get("/{plugin_id}/settings", summary="获取插件设置")
async def get_plugin_settings(
    plugin_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    """获取插件的设置信息"""
    if not await check_admin(current_user_id):
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    plugin = await PluginService.get_by_id(plugin_id)
    if not plugin:
        return ErrorResponse(msg="插件不存在", status_code=status.HTTP_404_NOT_FOUND)

    # 优先从已加载的插件实例获取 schema，否则从 manifest.json 读取
    schema = None
    plugin_instance = plugin_manager.get_plugin(plugin.name)
    if plugin_instance and hasattr(plugin_instance, 'get_settings_schema'):
        schema = plugin_instance.get_settings_schema()
    else:
        # 从 manifest.json 读取 settings_schema
        manifest = plugin_manager.get_manifest(plugin.name)
        if manifest:
            schema = manifest.get("settings_schema")

    return SuccessResponse(data={
        "settings": plugin.settings,
        "schema": schema,
    })


@router.put("/{plugin_id}/settings", summary="更新插件设置")
async def update_plugin_settings(
    plugin_id: int,
    settings_data: PluginSettingsUpdate,
    current_user_id: int = Depends(get_current_user_id),
):
    """更新插件设置"""
    if not await check_admin(current_user_id):
        return ErrorResponse(msg="无权限执行此操作", status_code=status.HTTP_403_FORBIDDEN)

    plugin = await PluginService.update_settings(plugin_id, settings_data.settings)
    if not plugin:
        return ErrorResponse(msg="插件不存在", status_code=status.HTTP_404_NOT_FOUND)

    # 如果插件已加载，通知插件实例更新设置
    plugin_instance = plugin_manager.get_plugin(plugin.name)
    if plugin_instance and hasattr(plugin_instance.module, 'on_settings_update'):
        try:
            await plugin_instance.module.on_settings_update(settings_data.settings)
        except Exception:
            pass  # 忽略设置更新回调错误

    return SuccessResponse(data=await plugin.to_dict(), msg="设置已更新")
