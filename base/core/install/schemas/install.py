from pydantic import BaseModel, Field
from typing import Optional

class DatabaseConfig(BaseModel):
    """数据库配置"""
    db_host: str = Field(default="127.0.0.1", description="数据库主机地址")
    db_port: int = Field(default=15432, description="数据库端口")
    db_name: str = Field(default="aipaneladmin", description="数据库名称")
    db_user: str = Field(default="admin", description="数据库用户名")
    db_password: str = Field(default="", description="数据库密码")
    charset: str = Field(default="UTF8", description="数据库字符集")
    minsize: int = Field(default=5, description="最小连接数")
    maxsize: int = Field(default=20, description="最大连接数")
    timeout: int = Field(default=30, description="连接超时时间")
    command_timeout: int = Field(default=30, description="命令执行超时时间")
    auto_create_db: bool = Field(default=False, description="数据库不存在时自动创建")

class AdminConfig(BaseModel):
    """管理员配置"""
    username: str = Field(default="admin", description="管理员用户名")
    password: str = Field(default="", description="管理员密码")
    email: str = Field(default="admin@example.com", description="管理员邮箱")
    alias: str = Field(default="系统管理员", description="管理员昵称")

class ServerConfig(BaseModel):
    """服务器基础配置"""
    app_port: int = Field(default=9998, description="应用端口")
    app_debug: bool = Field(default=False, description="调试模式")
    frontend_name: str = Field(default="", description="前端系统名称")
    backend_name: str = Field(default="", description="后台系统名称")

class InstallRequest(BaseModel):
    """安装请求"""
    database: DatabaseConfig = Field(..., description="数据库配置")
    admin: AdminConfig = Field(..., description="管理员配置")
    server: ServerConfig = Field(default_factory=ServerConfig, description="服务器配置")

class InstallStatusResponse(BaseModel):
    """安装状态响应"""
    installed: bool = Field(..., description="是否已安装")
    current_step: int = Field(default=0, description="当前步骤")
    message: str = Field(default="", description="状态消息")

class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    database: DatabaseConfig = Field(..., description="数据库配置")

class TestConnectionResponse(BaseModel):
    """测试连接响应"""
    success: bool = Field(..., description="是否成功（数据库连接且为空时才为 True）")
    message: str = Field(default="", description="结果消息")
    response_time_ms: int = Field(default=0, description="响应时间(毫秒)")
    is_empty: bool = Field(default=False, description="数据库是否为空（public schema 无用户表）")
    table_count: int = Field(default=-1, description="public schema 下的表总数，-1 表示未知")
