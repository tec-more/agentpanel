from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from base.core.install.schemas.install import (
    InstallRequest,
    InstallStatusResponse,
    TestConnectionRequest,
    TestConnectionResponse
)
from base.core.install.services.install_service import InstallService
from base.common.response import success_response
from base.common.setting import settings
import os
import sys
import platform

router = APIRouter(prefix="/v1/install", tags=["系统安装"])


@router.get("/env-check", summary="环境检测")
async def env_check():
    """检测运行环境，返回操作系统、Python版本、文件权限等信息"""
    import platform
    import sys
    from pathlib import Path
    from base.common.setting import settings

    # 操作系统检测
    os_name = platform.system()
    os_version = platform.version()
    if os_name == "Windows":
        os_display = f"Windows {os_version.split('.')[0]}"
    elif os_name == "Linux":
        os_display = f"Linux {platform.release()}"
    else:
        os_display = f"{os_name} {os_version}"

    # Python版本检测
    python_version = sys.version.split()[0]
    python_ok = sys.version_info >= (3, 8)

    # 文件写入权限检测
    checks = []
    base_path = Path(settings.base_path) if hasattr(settings, 'base_path') else Path.cwd()

    # 检测 config.conf 写入权限
    config_path = base_path / "config.conf"
    config_writable = False
    config_status = "warning"
    config_desc = "配置文件写入检测"
    try:
        test_file = base_path / ".write_test_config"
        test_file.touch()
        test_file.unlink()
        config_writable = True
        config_status = "success"
        config_desc = "config.conf 可写"
    except Exception:
        config_status = "error"
        config_desc = "config.conf 不可写"

    checks.append({
        "name": "配置文件写入权限",
        "value": config_status == "success" and "可写" or "不可写",
        "status": config_status,
        "desc": config_desc
    })

    # 检测 storage 目录写入权限
    storage_path = base_path / "storage"
    storage_writable = False
    storage_status = "warning"
    storage_desc = "存储目录检测"
    try:
        storage_path.mkdir(exist_ok=True)
        test_file = storage_path / ".write_test_storage"
        test_file.touch()
        test_file.unlink()
        storage_writable = True
        storage_status = "success"
        storage_desc = "storage 目录可写"
    except Exception:
        storage_status = "error"
        storage_desc = "storage 目录不可写"

    checks.append({
        "name": "存储目录写入权限",
        "value": storage_status == "success" and "可写" or "不可写",
        "status": storage_status,
        "desc": storage_desc
    })

    # 检测 logs 目录
    logs_path = base_path / "logs"
    logs_status = "warning"
    logs_desc = "日志目录检测"
    try:
        logs_path.mkdir(exist_ok=True)
        test_file = logs_path / ".write_test_logs"
        test_file.touch()
        test_file.unlink()
        logs_status = "success"
        logs_desc = "logs 目录可写"
    except Exception:
        logs_status = "error"
        logs_desc = "logs 目录不可写"

    checks.append({
        "name": "日志目录写入权限",
        "value": logs_status == "success" and "可写" or "不可写",
        "status": logs_status,
        "desc": logs_desc
    })

    # 检测数据库端口是否可用（仅检测端口是否空闲，不检测数据库本身）
    db_port = settings.db_port if hasattr(settings, 'db_port') else 15432
    port_available = True
    port_status = "warning"
    port_desc = f"数据库端口 {db_port} 待配置后检测"
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', db_port))
        if result == 0:
            port_available = True
            port_status = "success"
            port_desc = f"端口 {db_port} 已被占用（数据库可能已在运行）"
        else:
            port_available = True
            port_status = "warning"
            port_desc = f"端口 {db_port} 空闲（请在下一步配置数据库连接）"
        sock.close()
    except Exception:
        port_status = "warning"
        port_desc = f"端口 {db_port} 状态未知"

    checks.append({
        "name": "数据库端口",
        "value": f"{db_port}",
        "status": port_status,
        "desc": port_desc
    })

    # 汇总
    all_ok = all(c["status"] != "error" for c in checks)
    has_warning = any(c["status"] == "warning" for c in checks)

    return success_response({
        "os": {
            "name": os_name,
            "version": os_version,
            "display": os_display,
            "status": "success",
            "desc": "支持的操作系统"
        },
        "python": {
            "version": python_version,
            "status": "success" if python_ok else "error",
            "desc": "当前版本满足要求" if python_ok else "Python 版本过低，需要 3.8+"
        },
        "checks": checks,
        "overall_status": "success" if all_ok else ("warning" if has_warning else "error"),
        "message": "环境检测通过" if all_ok else ("部分检测项警告" if has_warning else "环境检测失败")
    })


@router.get("/status", summary="获取安装状态")
async def get_install_status():
    """获取系统安装状态"""
    installed = InstallService.is_installed()
    
    return success_response({
        "installed": installed,
        "current_step": 4 if installed else 0,
        "message": "系统已安装" if installed else "系统未安装，需要执行安装"
    })


@router.post("/test-database", response_model=TestConnectionResponse, summary="测试数据库连接")
async def test_database_connection(request: TestConnectionRequest):
    """测试数据库连接（含空库检测，非空数据库会返回 success=False 阻止安装）"""
    db = request.database

    success, message, response_time, is_empty, table_count = await InstallService.test_database_connection(
        db_host=db.db_host,
        db_port=db.db_port,
        db_name=db.db_name,
        db_user=db.db_user,
        db_password=db.db_password,
        charset=db.charset,
        timeout=5,
        auto_create_db=db.auto_create_db
    )

    return TestConnectionResponse(
        success=success,
        message=message,
        response_time_ms=response_time,
        is_empty=is_empty,
        table_count=table_count
    )


@router.post("/execute", summary="执行安装")
async def execute_installation(request: InstallRequest):
    """执行系统安装"""
    if InstallService.is_installed():
        raise HTTPException(
            status_code=400,
            detail="系统已安装，如需重新安装请先清除安装标记"
        )
    
    # 先测试数据库连接 + 空库检测
    db = request.database
    success, message, _, is_empty, table_count = await InstallService.test_database_connection(
        db_host=db.db_host,
        db_port=db.db_port,
        db_name=db.db_name,
        db_user=db.db_user,
        db_password=db.db_password,
        charset=db.charset,
        auto_create_db=db.auto_create_db
    )

    if not success:
        if table_count >= 0 and is_empty is False:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{message} | 该数据库中已有 {table_count} 张表，"
                    "可能包含旧数据。为避免数据丢失，系统禁止在非空数据库上强制安装。"
                    "请更换为空的数据库，或手动清空当前数据库后再试！"
                )
            )
        raise HTTPException(
            status_code=400,
            detail=f"数据库连接失败：{message}"
        )
    
    # 执行安装
    try:
        await InstallService.execute_installation(
            db_config={
                "db_host": db.db_host,
                "db_port": db.db_port,
                "db_name": db.db_name,
                "db_user": db.db_user,
                "db_password": db.db_password,
                "charset": db.charset,
                "minsize": db.minsize,
                "maxsize": db.maxsize,
                "timeout": db.timeout,
                "command_timeout": db.command_timeout,
                "auto_create_db": db.auto_create_db
            },
            admin_config={
                "username": request.admin.username,
                "password": request.admin.password,
                "email": request.admin.email,
                "alias": request.admin.alias
            },
            server_config={
                "app_port": request.server.app_port,
                "app_debug": request.server.app_debug,
                "frontend_name": request.server.frontend_name,
                "backend_name": request.server.backend_name
            }
        )

        # 安装成功，提示用户手动重启
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "系统安装成功！请手动重启应用服务后再登录。",
                "data": {
                    "admin_username": request.admin.username,
                    "admin_email": request.admin.email,
                    "need_restart": True
                }
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"安装失败：{str(e)}"
        )


@router.post("/reset", summary="重置安装状态（谨慎使用）")
async def reset_installation():
    """重置安装状态，允许重新安装"""
    InstallService.remove_install_marker()
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "安装标记已移除，可以重新执行安装"
        }
    )
