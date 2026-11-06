from . import config
import os
import typing
from pydantic_settings import BaseSettings
from typing import Any, List, Optional, Literal
from pathlib import Path


def get_discovered_plugins() -> List[str]:
	"""
	发现插件目录中所有带 manifest.json 的插件（不论安装/启用状态）
	"""
	plugins_dir = Path(__file__).parent.parent / "plugins"
	exclude_dirs = {"__pycache__", ".git", "_temp_install"}

	discovered = []
	if plugins_dir.exists() and plugins_dir.is_dir():
		for plugin in plugins_dir.iterdir():
			if plugin.is_dir() and not plugin.name.startswith("_") and plugin.name not in exclude_dirs:
				if (plugin / "manifest.json").exists():
					discovered.append(plugin.name)

	return discovered


def get_enabled_plugins() -> List[str]:
	"""
	从各插件的 manifest.json 读取已安装且激活的插件列表
	（供路由/功能门控使用；ORM 模型加载请用 get_model_list）
	"""
	import json
	plugins_dir = Path(__file__).parent.parent / "plugins"
	exclude_dirs = {"__pycache__", ".git"}

	enabled_plugins = []
	if plugins_dir.exists() and plugins_dir.is_dir():
		for plugin in plugins_dir.iterdir():
			if plugin.is_dir() and not plugin.name.startswith("_") and plugin.name not in exclude_dirs:
				manifest_file = plugin / "manifest.json"
				if manifest_file.exists():
					try:
						with open(manifest_file, "r", encoding="utf-8") as f:
							manifest = json.load(f)
							if manifest.get("is_installed") and manifest.get("is_enabled"):
								enabled_plugins.append(plugin.name)
					except Exception:
						pass

	return enabled_plugins


def get_plugin_models_from_manifest(plugin_name: str) -> List[str]:
	"""
	从插件的 manifest.json 读取模型列表
	"""
	import json
	plugins_dir = Path(__file__).parent.parent / "plugins"
	manifest_file = plugins_dir / plugin_name / "manifest.json"

	models = []
	if manifest_file.exists():
		try:
			with open(manifest_file, "r", encoding="utf-8") as f:
				manifest = json.load(f)
				# 检查是否有模型配置
				if manifest.get("models"):
					# 添加每个模型的具体路径
					for model_name in manifest.get("models", []):
						models.append(f"base.plugins.{plugin_name}.models.{model_name}")
		except Exception:
			pass

	return models


def get_model_list() -> List[str]:
	"""
	获取所有需要加载的模型列表
	- 核心模块的模型总是加载
	- 所有已发现插件（含未安装/未激活）的模型全部加载
	  加载模型只意味着表结构被注册/创建；
	  路由、菜单、事件处理器、定时任务等仍由 is_enabled 状态门控。
	  这样运行时安装/启用插件无需重启即可查询数据。
	"""
	plugin_models = []
	core_models = []

	# 加载核心模块的模型
	core_dir = Path(__file__).parent.parent / "core"
	if core_dir.exists() and core_dir.is_dir():
		for core_module in core_dir.iterdir():
			models_path = core_module / "models"
			if models_path.exists() and models_path.is_dir():
				for model_file in models_path.glob("*.py"):
					if model_file.name != "__init__.py":
						relative_model = f"base.core.{core_module.name}.models.{model_file.stem}"
						core_models.append(relative_model)

	# 加载所有已发现插件的模型（不论安装/激活状态）
	discovered_plugins = get_discovered_plugins()
	for plugin_name in discovered_plugins:
		models = get_plugin_models_from_manifest(plugin_name)
		plugin_models.extend(models)

	model_list = core_models + plugin_models + [
		"base.common.events.models.event_record",
		"base.common.events.models.replay_audit_log",
		# T1 新增公共层模型（Q1/Q2：base/common 非插件，显式注册，与插件启用态解耦 R-07）
		"base.common.quota.models.quota",
		# T4 套餐绑定关系（Q-D 映射，服务层维护）
		"base.common.quota.models.binding",
		"base.common.authz.models.resource_grant",
	] + ['aerich.models']
	return model_list

# 数据库配置
db_host: str = config.config.get("db", "db_host", fallback="127.0.0.1")
db_name: str = config.config.get("db", "db_name", fallback="aipaneladmin")
db_user: str = config.config.get("db", "db_user", fallback="admin")
db_password: str = config.config.get("db", "db_password", fallback="123456")
db_port: int = config.config.getint("db", "db_port", fallback=15432)
minsize: int = config.config.getint("db", "minsize", fallback=5)
maxsize: int = config.config.getint("db", "maxsize", fallback=20)
timeout: int = config.config.getint("db", "timeout", fallback=30)
command_timeout: int = config.config.getint("db", "command_timeout", fallback=30)
# 模块级别的TORTOISE_ORM配置，用于aerich命令
TORTOISE_ORM: dict = {
	"connections": {
		# SQLite configuration
		# "sqlite": {
		#     "engine": "tortoise.backends.sqlite",
		#     "credentials": {"file_path": f"{BASE_DIR}/db.sqlite3"},  # Path to SQLite database file
		# },
		# MySQL/MariaDB configuration
		# Install with: tortoise-orm[asyncmy]
		# "mysql": {
		#     "engine": "tortoise.backends.mysql",
		#     "credentials": {
		#         "host": "localhost",  # Database host address
		#         "port": 3306,  # Database port
		#         "user": "yourusername",  # Database username
		#         "password": "yourpassword",  # Database password
		#         "database": "yourdatabase",  # Database name
		#     },
		# },
		# PostgreSQL configuration
		# Install with: tortoise-orm[asyncpg]
		"postgres": {
			"engine": "tortoise.backends.asyncpg",
			"credentials": {
				"host": db_host,  # Database host address
				"port": db_port,  # Database port
				"user": db_user,  # Database username
				"password": db_password,  # Database password
				"database": db_name,  # Database name
				"ssl": False,  # Disable SSL
				# 连接池配置
				"minsize": minsize,       # 最小连接数（默认1）
				"maxsize": maxsize,      # 最大连接数（默认10）
				"timeout": timeout,      # 连接获取超时（秒）
				"command_timeout": command_timeout,  # 查询执行超时（秒）
				"statement_cache_size": 0,
			},
		},
		# MSSQL/Oracle configuration
		# Install with: tortoise-orm[asyncodbc]
		# "oracle": {
		#     "engine": "tortoise.backends.asyncodbc",
		#     "credentials": {
		#         "host": "localhost",  # Database host address
		#         "port": 1433,  # Database port
		#         "user": "yourusername",  # Database username
		#         "password": "yourpassword",  # Database password
		#         "database": "yourdatabase",  # Database name
		#     },
		# },
		# SQLServer configuration
		# Install with: tortoise-orm[asyncodbc]
		# "sqlserver": {
		#     "engine": "tortoise.backends.asyncodbc",
		#     "credentials": {
		#         "host": "localhost",  # Database host address
		#         "port": 1433,  # Database port
		#         "user": "yourusername",  # Database username
		#         "password": "yourpassword",  # Database password
		#         "database": "yourdatabase",  # Database name
		#     },
		# },
	},
	"apps": {
        "models": {
            "models": get_model_list(),
            "default_connection": "postgres",
        },
    },
	"use_tz": True,  # Whether to use timezone-aware datetimes
	"timezone": "Asia/Shanghai",  # Timezone setting
	"db_logs": False,  # 禁用 Tortoise ORM 的 SQL 日志输出
}

class Settings(BaseSettings):

	app_name: str = config.config.get("app", "name", fallback="AIPanelAdmin")
	app_description: str = config.config.get("app", "description", fallback="AIPanelAdmin API Documentation")
	app_version: str = config.config.get("app", "version", fallback="0.1.0")
	debug: bool = config.config.getboolean("app", "debug", fallback=True)
	# 系统名称与安装后跳转配置（安装向导写入）
	frontend_name: str = config.config.get("app", "frontend_name", fallback="")
	backend_name: str = config.config.get("app", "backend_name", fallback="")
	install_redirect: str = config.config.get("app", "install_redirect", fallback="login")
	db_host: str = db_host
	db_name: str = db_name
	db_user: str = db_user
	db_password: str = db_password
	db_port: int = db_port
	# 数据库连接池配置
	minsize: int = minsize
	maxsize: int = maxsize
	timeout: int = timeout
	command_timeout: int = command_timeout
	# Redis配置
	REDIS_ENABLED: bool = config.config.getboolean("redis", "enabled", fallback=False)
	REDIS_HOST: str = config.config.get("redis", "host", fallback="127.0.0.1")
	REDIS_PORT: int = config.config.getint("redis", "port", fallback=6379)
	REDIS_PASSWORD: str = config.config.get("redis", "password", fallback="")
	REDIS_DB: int = config.config.getint("redis", "db", fallback=0)
	# 部署环境与启动自检（上线硬约束 H-1/H-2；环境变量优先于 ini 配置）
	DEPLOY_ENV: str = os.environ.get("DEPLOY_ENV", config.config.get("deploy", "env", fallback="dev"))
	STRICT_STARTUP: bool = os.environ.get(
		"STRICT_STARTUP", config.config.get("deploy", "strict_startup", fallback="true")
	).lower() == "true"
	# 项目根目录
	base_path: Path = Path(__file__).parent.parent.parent
	LOG_DIR: str = config.config.get("log", "path", fallback=str(base_path / "logs"))
	STORAGE_DIR: str = config.config.get("storage", "path", fallback=str(base_path / "storage"))
	# ================================================= #
	# ******************** 跨域配置 ******************** #
	# ================================================= #
	CORS_ORIGIN_ENABLE: bool = True    # 是否启用跨域
	# ALLOW_ORIGINS: List[str] = ["*"]   # 允许的域名列表
	ALLOW_ORIGINS: List[str] = [
		'http://0.0.0.0:9998',
		'http://0.0.0.0:9999',
		'http://0.0.0.0:8000',
		'http://localhost:3000',
		'http://127.0.0.1:3000',
		'http://localhost:9999',
		'http://127.0.0.1:9999',
		'http://127.0.0.1:9998',
		'http://localhost:9998',
	]   # 允许的域名列表
	ALLOW_METHODS: List[str] = ["*"]   # 允许的HTTP方法
	ALLOW_HEADERS: List[str] = ["*"]   # 允许的请求头
	ALLOW_CREDENTIALS: bool = True     # 是否允许携带cookie
	CORS_EXPOSE_HEADERS: list[str] = ['X-Request-ID']	
	# ================================================= #	
	TORTOISE_ORM: dict = TORTOISE_ORM

	DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
	OPERATION_LOG_RECORD: bool = True
	
	# ================================================= #
	# ******************* 审计配置 ******************* #
	# ================================================= #
	AUDIT_ENABLED: bool = config.config.getboolean("audit", "enabled", fallback=True)
	AUDIT_RETAIN_DAYS: int = config.config.getint("audit", "retention_days", fallback=90)
	AUDIT_LOG_HTTP_REQUESTS: bool = config.config.getboolean("audit", "log_http_requests", fallback=True)
	AUDIT_LOG_DATA_CHANGES: bool = config.config.getboolean("audit", "log_data_changes", fallback=True)
	AUDIT_LOG_LOGIN: bool = config.config.getboolean("audit", "log_login", fallback=True)
	TRACE_ENABLED: bool = config.config.getboolean("audit", "trace_enabled", fallback=True)
	# ================================================= #
	# ******************* Gzip压缩配置 ******************* #
	# ================================================= #
	GZIP_ENABLE: bool = True        # 是否启用Gzip
	GZIP_MIN_SIZE: int = 1000       # 最小压缩大小(字节)
	GZIP_COMPRESS_LEVEL: int = 9    # 压缩级别(1-9)

	# ================================================= #
	# ******************* 邮件服务配置 ******************* #
	# ================================================= #
	EMAIL_ENABLED: bool = config.config.getboolean("email", "enabled", fallback=True)
	SMTP_HOST: str = config.config.get("email", "smtp_host", fallback="smtp.qq.com")
	SMTP_PORT: int = config.config.getint("email", "smtp_port", fallback=587)
	SMTP_USE_TLS: bool = config.config.getboolean("email", "smtp_use_tls", fallback=True)
	SENDER_EMAIL: str = config.config.get("email", "sender_email", fallback="")
	SENDER_PASSWORD: str = config.config.get("email", "sender_password", fallback="")
	SENDER_NAME: str = config.config.get("email", "sender_name", fallback="AIPanelAdmin")
	# ================================================= #
	# ******************* Qdrant 配置 ******************* #
	# ================================================= #
	QDRANT_ENABLED: bool = config.config.getboolean("qdrant", "enabled", fallback=True)
	QDRANT_HOST: str = config.config.get("qdrant", "host", fallback="http://localhost:6333")
	QDRANT_API_KEY: str = config.config.get("qdrant", "api_key", fallback="")
	QDRANT_TIMEOUT: int = config.config.getint("qdrant", "timeout", fallback=300)

	# ================================================= #
	# ******************* 监控配置 ******************* #
	# ================================================= #
	PROMETHEUS_ENABLED: bool = config.config.getboolean("monitoring", "prometheus_enabled", fallback=True)
	PROMETHEUS_PORT: int = config.config.getint("monitoring", "prometheus_port", fallback=9090)
	PROMETHEUS_PUSH_ENABLED: bool = config.config.getboolean("monitoring", "push_enabled", fallback=False)
	PROMETHEUS_PUSHGATEWAY: str = config.config.get("monitoring", "pushgateway", fallback="localhost:9091")
	PROMETHEUS_PUSH_INTERVAL: int = config.config.getint("monitoring", "push_interval", fallback=10)
	
	ELK_ENABLED: bool = config.config.getboolean("elk", "enabled", fallback=False)
	
	JAEGER_ENABLED: bool = config.config.getboolean("jaeger", "enabled", fallback=False)
	JAEGER_HOST: str = config.config.get("jaeger", "host", fallback="localhost")
	JAEGER_PORT: int = config.config.getint("jaeger", "port", fallback=6831)

	# ================================================= #
	# ******************* RabbitMQ配置 ******************* #
	# ================================================= #
	RABBITMQ_ENABLED: bool = config.config.getboolean("rabbitmq", "enabled", fallback=False)
	RABBITMQ_HOST: str = config.config.get("rabbitmq", "host", fallback="127.0.0.1")
	RABBITMQ_PORT: int = config.config.getint("rabbitmq", "port", fallback=5672)
	RABBITMQ_VIRTUAL_HOST: str = config.config.get("rabbitmq", "virtual_host", fallback="/")
	RABBITMQ_USERNAME: str = config.config.get("rabbitmq", "username", fallback="guest")
	RABBITMQ_PASSWORD: str = config.config.get("rabbitmq", "password", fallback="guest")
	# 心跳间隔（秒），0 表示禁用心跳，避免空闲连接被判定为 stuck
	RABBITMQ_HEARTBEAT: int = config.config.getint("rabbitmq", "heartbeat", fallback=0)
	RABBITMQ_EXCHANGE: str = config.config.get("rabbitmq", "exchange", fallback="event_bus.exchange")
	RABBITMQ_QUEUE_PREFIX: str = config.config.get("rabbitmq", "queue_prefix", fallback="event_bus")
	RABBITMQ_DLQ_NAME: str = config.config.get("rabbitmq", "dlq_name", fallback="event_bus.dlq")
	RABBITMQ_PREFETCH_COUNT: int = config.config.getint("rabbitmq", "prefetch_count", fallback=10)
	RABBITMQ_MAX_RETRIES: int = config.config.getint("rabbitmq", "max_retries", fallback=3)
	RABBITMQ_PUBLISH_CONFIRM_TIMEOUT: int = config.config.getint("rabbitmq", "publish_confirm_timeout", fallback=5)
	RABBITMQ_CONNECTION_RETRY_INTERVAL: int = config.config.getint("rabbitmq", "connection_retry_interval", fallback=5)
	RABBITMQ_DEGRADED_COOLDOWN: int = config.config.getint("rabbitmq", "degraded_cooldown", fallback=30)


settings = Settings()