import os
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class InstallService:
    """安装服务"""
    
    INSTALL_MARKER_FILE = ".installed"
    
    @classmethod
    def is_installed(cls) -> bool:
        """检查系统是否已安装"""
        marker_path = cls._get_marker_path()
        return marker_path.exists()
    
    @classmethod
    def mark_as_installed(cls) -> None:
        """标记为已安装"""
        marker_path = cls._get_marker_path()
        marker_path.touch()
    
    @classmethod
    def remove_install_marker(cls) -> None:
        """移除安装标记（用于重新安装）"""
        marker_path = cls._get_marker_path()
        if marker_path.exists():
            marker_path.unlink()
    
    @classmethod
    def _get_marker_path(cls) -> Path:
        """获取标记文件路径"""
        from base.common.setting import settings
        return Path(settings.base_path) / cls.INSTALL_MARKER_FILE
    
    @classmethod
    async def _try_connect(
        cls,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str,
        timeout: int = 5
    ) -> tuple[bool, str]:
        """尝试连接数据库，返回 (是否成功, 错误码)"""
        import asyncpg
        
        try:
            conn = await asyncpg.connect(
                host=db_host,
                port=db_port,
                user=db_user,
                password=db_password,
                database=db_name,
                timeout=timeout
            )
            await conn.execute("SELECT 1")
            await conn.close()
            return True, ""
        except Exception as e:
            error_str = str(e).lower()
            error_type = type(e).__name__.lower()
            
            # 数据库不存在的判断
            is_db_not_exist = (
                "invalidcatalogname" in error_type or
                ("not exist" in error_str and "database" in error_str) or
                ("does not exist" in error_str and "database" in error_str) or
                (db_name.lower() in error_str and ("not exist" in error_str or "does not exist" in error_str))
            )
            
            if is_db_not_exist:
                return False, "database_not_exist"
            
            # 账户被锁定 (openGauss 特定)
            if "locked" in error_str:
                return False, "account_locked"
            
            # 连接被拒绝（主机/端口问题）
            is_connection_refused = (
                "connectiondoesnotexisterror" in error_type or
                "connection refused" in error_str or
                "could not connect" in error_str
            )
            if is_connection_refused:
                return False, "connection_refused"
            
            # 密码错误/认证失败 (openGauss: InvalidAuthorizationSpecificationError)
            is_auth_error = (
                "invalidpassworderror" in error_type or
                "invalidauthorizationspecificationerror" in error_type or
                "invalid password" in error_str or
                "authentication failed" in error_str or
                "password" in error_str and ("invalid" in error_str or "error" in error_str)
            )
            if is_auth_error:
                return False, "auth_failed"
            
            # 超时
            if "timeout" in error_str:
                return False, "timeout"
            
            return False, f"unknown:{type(e).__name__}"
    
    @classmethod
    async def _connect_template_db(
        cls,
        db_host: str,
        db_port: int,
        db_user: str,
        db_password: str,
        timeout: int = 5
    ) -> tuple:
        """连接到模板数据库，返回 (conn, template_db_name) 或 (None, None)"""
        import asyncpg
        
        for template_db in ["postgres", "template1"]:
            try:
                conn = await asyncpg.connect(
                    host=db_host,
                    port=db_port,
                    user=db_user,
                    password=db_password,
                    database=template_db,
                    timeout=timeout
                )
                return conn, template_db
            except Exception:
                continue
        
        return None, None
    
    @classmethod
    async def create_database(
        cls,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str,
        charset: str = "UTF8",
        timeout: int = 10
    ) -> tuple[bool, str]:
        """创建数据库"""
        import asyncpg
        import re
        
        # 验证数据库名合法性（防止 SQL 注入）
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', db_name):
            return False, "数据库名不合法，只能包含字母、数字和下划线，且必须以字母或下划线开头"
        
        # 验证字符集
        valid_charsets = ['UTF8', 'LATIN1', 'GBK', 'GB18030', 'SQL_ASCII', 'UTF8MB4', 'GB18030']
        charset_upper = charset.upper()
        if charset_upper not in valid_charsets and charset_upper not in ['UTF8', 'UTF-8', 'UTF_8']:
            # 允许常见别名
            pass  # 宽松校验，让数据库自行处理
        
        # 连接到模板数据库
        conn, template_db = await cls._connect_template_db(
            db_host=db_host,
            db_port=db_port,
            db_user=db_user,
            db_password=db_password,
            timeout=timeout
        )
        
        if conn is None:
            return False, "无法连接到模板数据库，请检查用户名密码及用户的 CREATE DATABASE 权限"
        
        try:
            # openGauss/PostgreSQL 创建数据库，指定字符集
            charset_val = charset_upper
            try:
                # 先尝试带 ENCODING 的版本（openGauss 兼容）
                await conn.execute(f'CREATE DATABASE "{db_name}" ENCODING = \'{charset_val}\'')
            except Exception as e:
                error_str = str(e).lower()
                # 如果 ENCODING 语法不兼容，尝试其他语法
                if "encoding" in error_str or "syntax" in error_str or "syntax error" in error_str:
                    try:
                        await conn.execute(f'CREATE DATABASE "{db_name}" WITH ENCODING = \'{charset_val}\'')
                    except Exception as e2:
                        # 最后尝试最简版本
                        if "encoding" in str(e2).lower() or "syntax" in str(e2).lower():
                            await conn.execute(f'CREATE DATABASE "{db_name}"')
                        else:
                            raise
                else:
                    raise
            
            logger.info(f"数据库 {db_name} 创建成功 (字符集: {charset_val})")
            return True, f"数据库 {db_name} 创建成功（字符集: {charset_val}）"
            
        except asyncpg.exceptions.DuplicateDatabaseError:
            return True, f"数据库 {db_name} 已存在"
        except asyncpg.exceptions.InsufficientPrivilegeError:
            return False, "创建数据库失败：权限不足，请检查用户是否有 CREATE DATABASE 权限"
        except Exception as e:
            return False, f"创建数据库失败：{str(e)}"
        finally:
            if conn:
                await conn.close()
    
    @classmethod
    async def check_database_empty(
        cls,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str,
        timeout: int = 10
    ) -> tuple[bool, int, str]:
        """
        检查数据库是否为空（public schema 中没有任何用户表）。

        判断逻辑：
          - 查询 information_schema.tables 中 table_schema='public' 的所有表
          - 表数量 = 0 → 空库
          - 表数量 > 0 → 非空库（可能有旧数据，不能强制安装）

        Returns:
            (是否为空, 表数量, 说明/错误信息)
        """
        import asyncpg

        try:
            conn = await asyncpg.connect(
                host=db_host,
                port=db_port,
                user=db_user,
                password=db_password,
                database=db_name,
                timeout=timeout
            )
            try:
                # 统计 public schema 下的用户表数量
                count_sql = """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                """
                table_count = await conn.fetchval(count_sql) or 0

                # 如果表数很少（<=3），再判断一下是否全是系统/迁移表（aerich 等），
                # 避免把只有 aerich 迁移记录的库误判为"非空"
                is_empty = True
                if table_count > 0:
                    tables_sql = """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_type = 'BASE TABLE'
                    """
                    rows = await conn.fetch(tables_sql)
                    table_names = [r["table_name"] for r in rows]

                    # 系统/迁移表白名单（这些表存在也视为空库，允许安装）
                    system_table_prefixes = ("aerich", "pg_", "sql_", "information_schema")
                    non_system_tables = [
                        t for t in table_names
                        if not any(t.startswith(p) for p in system_table_prefixes)
                    ]

                    if non_system_tables:
                        is_empty = False
                        logger.warning(
                            f"[空库检测] 数据库 {db_name} 非空！"
                            f"总表数={table_count}, 用户表={len(non_system_tables)}, "
                            f"用户表样例: {non_system_tables[:5]}"
                        )
                    else:
                        is_empty = True
                        logger.info(
                            f"[空库检测] 数据库 {db_name} 仅含系统/迁移表 "
                            f"(共 {table_count} 张: {table_names})，视为空库"
                        )
                else:
                    logger.info(f"[空库检测] 数据库 {db_name} 为空（0 张用户表）")

                return is_empty, int(table_count), (
                    f"数据库为空，可正常安装" if is_empty
                    else f"数据库非空（已有 {table_count} 张表，含 {', '.join(non_system_tables[:3])} 等用户表）"
                )

            finally:
                await conn.close()

        except Exception as e:
            # 连接失败等情况，保守返回 False（未知），让调用方处理
            logger.warning(f"[空库检测] 查询失败: {e}")
            return False, -1, f"空库检测失败：{e}"

    @classmethod
    async def test_database_connection(
        cls,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str,
        charset: str = "UTF8",
        timeout: int = 5,
        auto_create_db: bool = False
    ) -> tuple[bool, str, int, bool, int]:
        """测试数据库连接

        Returns:
            (是否成功, 消息, 响应时间ms, 是否空库, 表数量)
            空库/表数量在连接失败时为 False/-1
        """
        import time

        start_time = time.time()

        # Step 1: 直接尝试连接目标数据库
        ok, error_code = await cls._try_connect(
            db_host=db_host,
            db_port=db_port,
            db_name=db_name,
            db_user=db_user,
            db_password=db_password,
            timeout=timeout
        )

        response_time = int((time.time() - start_time) * 1000)

        # 连接成功 → 做一次空库检测
        if ok:
            is_empty, table_count, empty_msg = await cls.check_database_empty(
                db_host=db_host,
                db_port=db_port,
                db_name=db_name,
                db_user=db_user,
                db_password=db_password
            )
            if is_empty:
                return True, "数据库连接成功（空库，可正常安装）", response_time, True, table_count
            else:
                # 连接成功但数据库非空 → 仍返回 success=False，阻止后续安装
                return (
                    False,
                    f"数据库连接成功，但{empty_msg}。请更换为空的数据库后再安装！",
                    response_time,
                    False,
                    table_count
                )
        
        # 根据错误码处理
        if error_code == "auth_failed":
            return False, "数据库连接失败：用户名或密码错误", 0, False, -1

        if error_code == "account_locked":
            return False, "数据库连接失败：账户已被锁定，请使用 omm 管理员解锁或重置密码", 0, False, -1

        if error_code == "connection_refused":
            return False, f"数据库连接失败：主机 {db_host}:{db_port} 无法访问", 0, False, -1

        if error_code == "timeout":
            return False, f"数据库连接超时：超过 {timeout} 秒", 0, False, -1

        # 数据库不存在
        if error_code == "database_not_exist":
            if auto_create_db:
                # Step 2: 尝试连接模板库创建数据库
                create_ok, create_msg = await cls.create_database(
                    db_host=db_host,
                    db_port=db_port,
                    db_name=db_name,
                    db_user=db_user,
                    db_password=db_password,
                    charset=charset
                )

                if not create_ok:
                    response_time = int((time.time() - start_time) * 1000)
                    return False, f"数据库 {db_name} 不存在，且自动创建失败：{create_msg}", response_time, False, -1

                # Step 3: 创建成功，再次连接验证 + 空库检测（刚创建的库必然为空）
                verify_ok, verify_error = await cls._try_connect(
                    db_host=db_host,
                    db_port=db_port,
                    db_name=db_name,
                    db_user=db_user,
                    db_password=db_password,
                    timeout=timeout
                )

                response_time = int((time.time() - start_time) * 1000)

                if verify_ok:
                    # 刚创建的数据库 → 视为空库（表数=0），直接返回成功
                    return (
                        True,
                        f"数据库连接成功（已自动创建空数据库 {db_name}）",
                        response_time,
                        True,
                        0
                    )
                else:
                    return False, f"数据库创建成功但连接验证失败：{verify_error}", response_time, False, -1
            else:
                response_time = int((time.time() - start_time) * 1000)
                return (
                    False,
                    f"数据库 {db_name} 不存在，请勾选下方「自动创建数据库」复选框后重试",
                    response_time,
                    False,
                    -1
                )

        # 其他未知错误
        if error_code.startswith("unknown:"):
            return False, f"数据库连接失败：{error_code[8:]}", response_time, False, -1
        return False, f"数据库连接失败：{error_code}", response_time, False, -1
    
    @classmethod
    async def write_config(
        cls,
        db_host: str,
        db_port: int,
        db_name: str,
        db_user: str,
        db_password: str,
        minsize: int = 5,
        maxsize: int = 20,
        timeout: int = 30,
        command_timeout: int = 30,
        app_port: int = 9998,
        app_debug: bool = False,
        frontend_name: str = "",
        backend_name: str = ""
    ) -> None:
        """写入配置文件"""
        import configparser
        from base.common.setting import settings
        
        config_path = Path(settings.base_path) / "config.conf"
        config = configparser.ConfigParser()
        
        if config_path.exists():
            config.read(config_path, encoding="utf-8")
        
        if not config.has_section("db"):
            config.add_section("db")
        
        config.set("db", "db_host", db_host)
        config.set("db", "db_port", str(db_port))
        config.set("db", "db_name", db_name)
        config.set("db", "db_user", db_user)
        config.set("db", "db_password", db_password)
        config.set("db", "minsize", str(minsize))
        config.set("db", "maxsize", str(maxsize))
        config.set("db", "timeout", str(timeout))
        config.set("db", "command_timeout", str(command_timeout))
        
        if not config.has_section("app"):
            config.add_section("app")
        
        config.set("app", "debug", str(app_debug).lower())
        config.set("app", "frontend_name", frontend_name)
        config.set("app", "backend_name", backend_name)
        
        with open(config_path, "w", encoding="utf-8") as f:
            config.write(f)
        
        # 更新内存中的设置
        settings.db_host = db_host
        settings.db_port = db_port
        settings.db_name = db_name
        settings.db_user = db_user
        settings.db_password = db_password
        settings.minsize = minsize
        settings.maxsize = maxsize
        settings.timeout = timeout
        settings.command_timeout = command_timeout
        settings.debug = app_debug
        # aipaneladmin 的 Settings 未定义 frontend_name/backend_name 字段，
        # Pydantic v2 对未定义字段赋值会抛 ValueError，这里防御式处理
        if hasattr(settings, "frontend_name"):
            settings.frontend_name = frontend_name
        if hasattr(settings, "backend_name"):
            settings.backend_name = backend_name
        
        # 更新 setting 模块级变量（TORTOISE_ORM 初始化时使用的是模块级变量）
        import base.common.setting as setting_module
        setting_module.db_host = db_host
        setting_module.db_port = db_port
        setting_module.db_name = db_name
        setting_module.db_user = db_user
        setting_module.db_password = db_password
        setting_module.minsize = minsize
        setting_module.maxsize = maxsize
        setting_module.timeout = timeout
        setting_module.command_timeout = command_timeout
        
        # 更新 TORTOISE_ORM 配置
        from base.common.setting import TORTOISE_ORM
        TORTOISE_ORM["connections"]["postgres"]["credentials"].update({
            "host": db_host,
            "port": db_port,
            "user": db_user,
            "password": db_password,
            "database": db_name,
            "minsize": minsize,
            "maxsize": maxsize,
            "timeout": timeout,
            "command_timeout": command_timeout,
        })
        
        logger.info(f"配置已写入: {config_path}")
    
    @classmethod
    async def initialize_database(cls) -> None:
        """初始化数据库"""
        from base.common.database import init_data
        await init_data()
        logger.info("数据库初始化完成")
    
    @classmethod
    async def create_admin_user(
        cls,
        username: str,
        password: str,
        email: str,
        alias: str = "系统管理员"
    ) -> None:
        """创建管理员用户"""
        from base.core.users.models.users import User
        from base.common.security import get_password_hash
        
        existing_user = await User.filter(username=username).first()
        if existing_user:
            logger.warning(f"用户 {username} 已存在，更新密码")
            existing_user.password = get_password_hash(password)
            existing_user.email = email
            existing_user.alias = alias
            existing_user.is_superuser = True
            existing_user.is_active = True
            await existing_user.save()
        else:
            await User.create(
                username=username,
                password=get_password_hash(password),
                email=email,
                alias=alias,
                is_superuser=True,
                is_active=True
            )
            logger.info(f"管理员用户 {username} 创建成功")
    
    @classmethod
    async def verify_database_written(
        cls,
        admin_username: str,
        retries: int = 0,
        retry_interval: float = 2.0,
        max_total_seconds: int = 0
    ) -> tuple[bool, str]:
        """
        校验数据库写入是否真正完成（表+数据双重验证）。

        ⚠️  关键策略（对应 "校验需要一直重试直到成功"）：
          - retries=0 或 max_total_seconds=0 时 → **无限重试**，直到通过才返回
          - 表不存在 / 列不存在 / 管理员行不存在 / 查询抛异常 → 都视为「DB 写入还在进行」，
            继续 sleep 后重试，绝不当成「最终失败」
          - 唯一失败出口：超过显式设置的 retries 或 max_total_seconds（一般不设置）

        验证内容：
          1. 数据库可连接可查询（SELECT 1）
          2. 用户表存在（通过 information_schema 动态匹配，列名包含 username/password 等）
          3. 通过动态列名查询，确认 admin_username 对应的数据行已写入

        Args:
            admin_username: 管理员用户名
            retries: 最大重试次数，0 = 不限制（无限重试）
            retry_interval: 每次重试间隔（秒）
            max_total_seconds: 总耗时上限（秒），0 = 不限制

        Returns:
            (是否通过, 详细说明)
        """
        import asyncpg
        from base.common.setting import settings

        attempt = 0
        start_time = time.time()
        last_error = "（初始化中，尚未执行校验）"

        while True:
            attempt += 1

            # ---- 退出条件判断（仅在设置了上限时触发） ----
            if retries > 0 and attempt > retries:
                return (
                    False,
                    f"数据库写入校验失败（已重试{retries}次，达到上限）: {last_error}"
                )
            if max_total_seconds > 0 and (time.time() - start_time) > max_total_seconds:
                return (
                    False,
                    f"数据库写入校验失败（已等待{int(time.time()-start_time)}秒，超时）: {last_error}"
                )

            attempt_label = (
                f"{attempt}" if retries == 0 else f"{attempt}/{retries}"
            )

            try:
                conn = await asyncpg.connect(
                    host=settings.db_host,
                    port=settings.db_port,
                    user=settings.db_user,
                    password=settings.db_password,
                    database=settings.db_name,
                    timeout=15
                )
                try:
                    # ---- 验证 1: 数据库可查询 ----
                    await conn.execute("SELECT 1")

                    # ---- 验证 2: 查找用户表（先看表名，再看列名来兜底识别） ----
                    # 候选表名（实际 User.Meta table = "user"）
                    table_name_candidates = (
                        "user", "users", "system_user", "system_users",
                        "admin_user", "admin_users"
                    )
                    table_sql = """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_type = 'BASE TABLE'
                    """
                    all_tables = [r["table_name"] for r in await conn.fetch(table_sql)]

                    # 先按表名命中
                    user_table = None
                    for t in table_name_candidates:
                        if t in all_tables:
                            user_table = t
                            break
                    # 命不中就按列名兜底：找一张表同时包含 "username"/"password"/"is_superuser"
                    if user_table is None:
                        for t in all_tables:
                            cols_sql = """
                                SELECT column_name
                                FROM information_schema.columns
                                WHERE table_schema = 'public' AND table_name = $1
                            """
                            cols = [r["column_name"] for r in await conn.fetch(cols_sql, t)]
                            if (
                                any(c in cols for c in ("username", "user_name", "login_name"))
                                and "password" in cols
                            ):
                                user_table = t
                                logger.warning(
                                    f"[DB校验-{attempt_label}] 未按表名找到用户表，"
                                    f"通过列特征识别为: {t}（列: {cols[:6]}）"
                                )
                                break

                    if user_table is None:
                        last_error = (
                            f"用户表尚未创建（共 {len(all_tables)} 张表: "
                            f"{all_tables[:10]}）"
                        )
                        logger.warning(f"[DB校验-{attempt_label}] {last_error}")
                        await asyncio.sleep(retry_interval)
                        continue

                    # ---- 验证 3: 读取用户表的真实列名 ----
                    cols_sql = """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = $1
                    """
                    cols = [r["column_name"] for r in await conn.fetch(cols_sql, user_table)]

                    # 映射：语义列名 → 真实列名
                    def _find_col(*semantic_names):
                        for s in semantic_names:
                            for c in cols:
                                if c.lower() == s.lower():
                                    return c
                        return None

                    real_col_username = _find_col("username", "user_name", "login_name", "name")
                    real_col_super = _find_col("is_superuser", "superuser", "is_admin", "admin")
                    real_col_active = _find_col("is_active", "active", "status")

                    if not real_col_username:
                        last_error = (
                            f"用户表 {user_table} 已找到，但缺少 username 类列，"
                            f"当前列: {cols}"
                        )
                        logger.warning(f"[DB校验-{attempt_label}] {last_error}")
                        await asyncio.sleep(retry_interval)
                        continue

                    logger.info(
                        f"[DB校验-{attempt_label}] 用户表={user_table}, "
                        f"总表数={len(all_tables)}, "
                        f"列映射: username→{real_col_username}, "
                        f"super→{real_col_super or '未识别'}, "
                        f"active→{real_col_active or '未识别'}"
                    )

                    # ---- 验证 4: 用真实列名查管理员数据 ----
                    select_cols = ["*"]  # 保守用 SELECT *，避免遗漏列
                    query_sql = (
                        f"SELECT {', '.join(select_cols)} "
                        f'FROM "{user_table}" '
                        f'WHERE "{real_col_username}" = $1'
                    )
                    admin_row = await conn.fetchrow(query_sql, admin_username)

                    if not admin_row:
                        last_error = (
                            f"管理员 {admin_username} 数据行尚未写入 "
                            f"(表 {user_table}.{real_col_username} 无匹配)"
                        )
                        logger.warning(f"[DB校验-{attempt_label}] {last_error}")
                        await asyncio.sleep(retry_interval)
                        continue

                    # 把 asyncpg Record 转成 dict，便于安全访问
                    admin_dict = dict(admin_row)

                    def _safe_get(d, *keys):
                        for k in keys:
                            if k in d and d[k] is not None:
                                return d[k]
                            kl = k.lower()
                            for dk, dv in d.items():
                                if dk.lower() == kl and dv is not None:
                                    return dv
                        return None

                    super_val = _safe_get(
                        admin_dict,
                        real_col_super or "", "is_superuser", "superuser", "is_admin"
                    )
                    active_val = _safe_get(
                        admin_dict,
                        real_col_active or "", "is_active", "active", "status"
                    )

                    logger.info(
                        f"[DB校验-{attempt_label}] ✅ 管理员数据写入成功: "
                        f"username={admin_username}, "
                        f"superuser={super_val}, active={active_val}"
                    )

                    # ---- 验证 5: 额外核心表（仅记录日志，不卡点） ----
                    extra_tables = [
                        "role", "roles", "permission", "permissions",
                        "menu", "menus", "audit_log", "audit_logs",
                        "role_permission", "role_permissions",
                        "user_role", "user_roles", "dept", "department", "departments"
                    ]
                    extra_hit = sum(1 for t in extra_tables if t in all_tables)
                    logger.info(
                        f"[DB校验-{attempt_label}] 额外核心表匹配: "
                        f"{extra_hit}/{len(extra_tables)}"
                    )

                    return True, (
                        f"数据库写入校验通过（第{attempt}次, 耗时{int(time.time()-start_time)}s）: "
                        f"用户表 {user_table} 存在, 管理员 {admin_username} 已写入且可查询, "
                        f"额外核心表 {extra_hit}/{len(extra_tables)}"
                    )

                finally:
                    try:
                        await conn.close(timeout=5)
                    except Exception:
                        pass

            except Exception as e:
                # 任意异常（连接失败、表不存在、列不存在、SQL 错误等）
                # 都视为「写入还没完成」→ 继续重试，不判最终失败
                last_error = f"{type(e).__name__}: {e}"
                logger.warning(
                    f"[DB校验-{attempt_label}] 校验异常，{retry_interval}s 后继续重试: {last_error}"
                )
                await asyncio.sleep(retry_interval)

    @classmethod
    def verify_install_files(cls) -> tuple[bool, str]:
        """
        校验安装相关文件是否都已正确写入。

        验证内容：
          1. .installed 标记文件存在
          2. config.conf 文件存在且包含关键配置（db 段 + app 段）

        Returns:
            (是否通过, 详细说明)
        """
        import configparser
        from base.common.setting import settings

        errors = []

        # ---- 验证 1: .installed 文件 ----
        marker_path = cls._get_marker_path()
        if not marker_path.exists():
            errors.append(f".installed 文件不存在: {marker_path}")
        else:
            logger.info(f"[文件校验] .installed 存在: {marker_path}")

        # ---- 验证 2: config.conf 文件 ----
        config_path = Path(settings.base_path) / "config.conf"
        if not config_path.exists():
            errors.append(f"config.conf 文件不存在: {config_path}")
        else:
            config = configparser.ConfigParser()
            try:
                config.read(config_path, encoding="utf-8")
            except Exception as e:
                errors.append(f"config.conf 解析失败: {e}")
            else:
                # 检查 db 段关键字段
                db_required = ["db_host", "db_port", "db_name", "db_user", "db_password"]
                if not config.has_section("db"):
                    errors.append("config.conf 缺少 [db] 段")
                else:
                    for key in db_required:
                        if not config.has_option("db", key) or not config.get("db", key):
                            errors.append(f"config.conf [db] 段缺少或为空: {key}")

                # 检查 app 段关键字段
                app_required = ["debug", "frontend_name", "backend_name"]
                if not config.has_section("app"):
                    errors.append("config.conf 缺少 [app] 段")
                else:
                    for key in app_required:
                        if not config.has_option("app", key):
                            # frontend_name / backend_name 允许为空字符串，只检查 key 是否存在
                            if key not in ("frontend_name", "backend_name"):
                                errors.append(f"config.conf [app] 段缺少: {key}")

                if not errors:
                    db_host = config.get("db", "db_host")
                    db_name = config.get("db", "db_name")
                    frontend = config.get("app", "frontend_name") or "(空)"
                    backend = config.get("app", "backend_name") or "(空)"
                    logger.info(
                        f"[文件校验] config.conf 内容正确: "
                        f"db={db_host}/{db_name}, frontend={frontend}, backend={backend}"
                    )

        if errors:
            return False, "文件校验失败: " + "; ".join(errors)
        return True, "文件校验通过: .installed 存在 + config.conf 配置完整"

    @classmethod
    async def verify_installation_complete(
        cls,
        admin_username: str,
        db_retries: int = 0,                # 0 = 不限次数
        db_retry_interval: float = 2.0,
        max_total_seconds: int = 0          # 0 = 不限总时长
    ) -> tuple[bool, str]:
        """
        完整校验：安装是否真的完成了？

        ⚠️  默认无限重试，直到全部通过（对应「校验要一直持续直到成功」）。
        一般不建议设置 db_retries / max_total_seconds 上限。

        流程：
          1. 循环执行：
             - 文件层校验（.installed + config.conf，瞬时操作，若失败则重试）
             - 数据库层校验（内部本身就是无限循环，直到通过）
          2. 两者都通过 → 返回 True

        Returns:
            (是否完成, 详细说明)
        """
        attempt = 0
        start_time = time.time()
        while True:
            attempt += 1
            logger.info(
                f"========== [完整校验 第{attempt}轮] 开始 =========="
            )

            # ---- 退出条件（仅在设置了上限时生效） ----
            if max_total_seconds > 0 and (time.time() - start_time) > max_total_seconds:
                return (
                    False,
                    f"安装完整校验超时（已等待{int(time.time()-start_time)}秒），仍未通过"
                )

            # ---- 文件层校验 ----
            files_ok, files_msg = cls.verify_install_files()
            if not files_ok:
                logger.warning(
                    f"[完整校验 第{attempt}轮] 文件层未通过: {files_msg}, "
                    f"{db_retry_interval}s 后重跑整轮..."
                )
                await asyncio.sleep(db_retry_interval)
                continue

            # ---- 数据库层校验（内部已带无限重试，不会失败返回，除非设了上限） ----
            db_ok, db_msg = await cls.verify_database_written(
                admin_username=admin_username,
                retries=db_retries,
                retry_interval=db_retry_interval,
                max_total_seconds=max_total_seconds
            )
            if not db_ok:
                # 只有设了上限才会走到这里
                logger.error(f"[完整校验 第{attempt}轮] DB层未通过（达到上限）: {db_msg}")
                return False, db_msg

            summary = (
                f"安装完成校验全部通过（总耗时{int(time.time()-start_time)}s） | "
                f"{files_msg} | {db_msg}"
            )
            logger.info(f"========== {summary} ==========")
            return True, summary

    @classmethod
    async def execute_installation(
        cls,
        db_config: dict,
        admin_config: dict,
        server_config: dict
    ) -> None:
        """执行完整安装流程"""
        try:
            import asyncio

            db_host = db_config["db_host"]
            db_port = db_config["db_port"]
            db_name = db_config["db_name"]
            db_user = db_config["db_user"]
            db_password = db_config["db_password"]
            db_charset = db_config.get("charset", "UTF8")
            auto_create_db = db_config.get("auto_create_db", True)
            admin_username = admin_config["username"]

            # Step 0: 确保数据库存在（如果勾选了自动创建）
            if auto_create_db:
                # 尝试直接连接目标数据库
                ok, error_code = await cls._try_connect(
                    db_host=db_host,
                    db_port=db_port,
                    db_name=db_name,
                    db_user=db_user,
                    db_password=db_password,
                    timeout=5
                )

                if not ok and error_code == "database_not_exist":
                    # 数据库不存在，尝试创建
                    create_ok, create_msg = await cls.create_database(
                        db_host=db_host,
                        db_port=db_port,
                        db_name=db_name,
                        db_user=db_user,
                        db_password=db_password,
                        charset=db_charset
                    )
                    if not create_ok:
                        raise RuntimeError(f"数据库 {db_name} 不存在且自动创建失败：{create_msg}")
                    logger.info(f"安装流程：{create_msg}")

            # Step 0.5: 强制空库校验（防御性检查，防止绕过 API 直调服务）
            is_empty, table_count, empty_msg = await cls.check_database_empty(
                db_host=db_host,
                db_port=db_port,
                db_name=db_name,
                db_user=db_user,
                db_password=db_password
            )
            if not is_empty:
                raise RuntimeError(
                    f"安装被拒绝：{empty_msg}。"
                    f"为避免数据丢失，禁止在非空数据库（共 {table_count} 张表）上强制安装。"
                    "请更换为空的数据库，或手动清空后再试。"
                )
            logger.info(f"[安装流程] 空库校验通过: {empty_msg}")

            # Step 1: 写入配置
            await cls.write_config(
                db_host=db_host,
                db_port=db_port,
                db_name=db_name,
                db_user=db_user,
                db_password=db_password,
                minsize=db_config.get("minsize", 5),
                maxsize=db_config.get("maxsize", 20),
                timeout=db_config.get("timeout", 30),
                command_timeout=db_config.get("command_timeout", 30),
                app_port=server_config.get("app_port", 9998),
                app_debug=server_config.get("app_debug", False),
                frontend_name=server_config.get("frontend_name", ""),
                backend_name=server_config.get("backend_name", "")
            )

            # Step 2: 初始化数据库（建表 + 迁移）
            await cls.initialize_database()

            # Step 3: 创建管理员
            await cls.create_admin_user(
                username=admin_config["username"],
                password=admin_config["password"],
                email=admin_config["email"],
                alias=admin_config.get("alias", "系统管理员")
            )

            # Step 4: 标记为已安装
            cls.mark_as_installed()

            # Step 5: 一次性数据一致性检查（有限重试）
            # 用于确认管理员数据是否已真正落盘；失败仅记录警告，不阻塞安装流程
            try:
                quick_ok, quick_msg = await cls.verify_database_written(
                    admin_username=admin_username,
                    retries=5,
                    retry_interval=0.8,
                    max_total_seconds=12
                )
                if quick_ok:
                    logger.info(f"[安装流程] 数据库写入校验通过: {quick_msg}")
                else:
                    logger.warning(
                        f"[安装流程] 数据库写入校验未通过（达上限）: {quick_msg}；"
                        "数据可能仍在写入中，请在重启服务后确认功能正常"
                    )
            except Exception as ve:
                logger.warning(
                    f"[安装流程] 数据库写入校验异常: {ve}；"
                    "安装标记已写入，功能将在重启服务后可用"
                )

            logger.info("安装流程执行完成")

        except Exception as e:
            logger.error(f"安装流程执行失败: {e}")
            raise
