"""
邮件服务 - 发送验证码

验证码存储与频率限制采用「Redis 优先、进程内降级」策略：
- 生产（Redis 启用）时，验证码写入 Redis 并带 TTL，多个 worker 共享、重启不丢；
- Redis 不可用时降级为进程内字典（仅单 worker / 本地开发可用，多 worker 不保证一致）。
"""
from __future__ import annotations

import time
import random
import string
import asyncio
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except Exception:  # pragma: no cover - redis 未安装时禁用
    _REDIS_AVAILABLE = False

from base.common.setting import settings

logger = logging.getLogger(__name__)


class EmailService:
    """邮件服务类"""

    # 验证码有效期（分钟）
    CODE_EXPIRE_MINUTES = 5

    # 验证码长度
    CODE_LENGTH = 6

    # ------------------------------------------------------------------ #
    # 频率限制（防刷）
    # ------------------------------------------------------------------ #
    # 同一邮箱在窗口内最多发送次数
    RATE_LIMIT_PER_EMAIL_WINDOW = 60  # 秒
    RATE_LIMIT_PER_EMAIL_MAX = 3
    # 同一 IP 在窗口内最多发送次数（兜底防批量刷）
    RATE_LIMIT_PER_IP_WINDOW = 60  # 秒
    RATE_LIMIT_PER_IP_MAX = 10

    # 进程内降级存储
    _verification_codes: Dict[str, str] = {}
    _code_expire_time: Dict[str, datetime] = {}
    _rate_store: Dict[str, List[float]] = {}

    # 懒加载的 Redis 客户端（模块级单例）
    _redis = None

    # ------------------------------------------------------------------ #
    # Redis 客户端
    # ------------------------------------------------------------------ #
    @classmethod
    def _redis_client(cls):
        if not _REDIS_AVAILABLE or not getattr(settings, "REDIS_ENABLED", False):
            return None
        if cls._redis is None:
            try:
                cls._redis = aioredis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD or None,
                    db=settings.REDIS_DB,
                    decode_responses=True,
                )
            except Exception as e:  # pragma: no cover
                logger.warning(f"[验证码] Redis 客户端创建失败，使用进程内存储: {e}")
                return None
        return cls._redis

    @classmethod
    def _code_key(cls, code_type: str, email: str) -> str:
        return f"vc:{code_type}:{email}"

    @classmethod
    def _rate_key_email(cls, email: str) -> str:
        return f"vc:rate:e:{email}"

    @classmethod
    def _rate_key_ip(cls, ip: str) -> str:
        return f"vc:rate:ip:{ip}"

    # ------------------------------------------------------------------ #
    # 验证码生成
    # ------------------------------------------------------------------ #
    @classmethod
    def generate_code(cls) -> str:
        """生成6位数字验证码"""
        return ''.join(random.choices(string.digits, k=cls.CODE_LENGTH))

    # ------------------------------------------------------------------ #
    # 验证码存储（Redis 优先，进程内降级）
    # ------------------------------------------------------------------ #
    @classmethod
    async def store_code(cls, email: str, code: str, code_type: str) -> None:
        """存储验证码，写入 Redis（带 TTL）或进程内字典"""
        key = cls._code_key(code_type, email)
        ttl = cls.CODE_EXPIRE_MINUTES * 60
        r = cls._redis_client()
        if r is not None:
            try:
                await r.set(key, code, ex=ttl)
                return
            except Exception as e:
                logger.warning(f"[验证码存储] Redis 写入失败，降级进程内: {e}")
        cls._verification_codes[key] = code
        cls._code_expire_time[key] = datetime.now() + timedelta(seconds=ttl)
        logger.info(f"[验证码存储] Email={email}, Type={code_type}, Code={code}, Key={key}")

    @classmethod
    async def verify_code(cls, email: str, code: str, code_type: str) -> bool:
        """验证验证码（一次有效，验证成功后删除）"""
        key = cls._code_key(code_type, email)
        r = cls._redis_client()
        if r is not None:
            try:
                stored = await r.get(key)
                if not stored:
                    logger.warning(f"[验证码验证失败] 不存在或已过期: {key}")
                    return False
                if stored == code:
                    await r.delete(key)
                    logger.info(f"[验证码验证成功] {key}")
                    return True
                logger.warning(f"[验证码验证失败] 不匹配 key={key}")
                return False
            except Exception as e:
                logger.warning(f"[验证码验证] Redis 读取失败，降级进程内: {e}")

        # 进程内降级
        logger.info(f"[验证码验证] key={key}")
        if key not in cls._verification_codes:
            logger.warning(f"[验证码验证失败] 验证码不存在: {key}")
            return False
        if datetime.now() > cls._code_expire_time[key]:
            cls._verification_codes.pop(key, None)
            cls._code_expire_time.pop(key, None)
            logger.warning(f"[验证码验证失败] 验证码已过期: {key}")
            return False
        if cls._verification_codes[key] == code:
            cls._verification_codes.pop(key, None)
            cls._code_expire_time.pop(key, None)
            logger.info(f"[验证码验证成功] 验证码匹配: {key}")
            return True
        logger.warning(f"[验证码验证失败] 验证码不匹配 key={key}")
        return False

    # ------------------------------------------------------------------ #
    # 频率限制（返回 None 表示通过，返回字符串表示被限流的提示）
    # ------------------------------------------------------------------ #
    @classmethod
    async def check_rate_limit(cls, email: str, ip: Optional[str] = None) -> Optional[str]:
        r = cls._redis_client()
        if r is not None:
            try:
                ek = cls._rate_key_email(email)
                cnt = await r.incr(ek)
                if cnt == 1:
                    await r.expire(ek, cls.RATE_LIMIT_PER_EMAIL_WINDOW)
                if cnt > cls.RATE_LIMIT_PER_EMAIL_MAX:
                    ttl = max(await r.ttl(ek), 1)
                    return f"该邮箱发送过于频繁，请 {ttl} 秒后重试"
                if ip:
                    ik = cls._rate_key_ip(ip)
                    ic = await r.incr(ik)
                    if ic == 1:
                        await r.expire(ik, cls.RATE_LIMIT_PER_IP_WINDOW)
                    if ic > cls.RATE_LIMIT_PER_IP_MAX:
                        ttl = max(await r.ttl(ik), 1)
                        return f"发送过于频繁，请 {ttl} 秒后重试"
                return None
            except Exception as e:
                logger.warning(f"[验证码限流] Redis 异常，降级进程内限流: {e}")
                return cls._fallback_rate_limit(email, ip)
        return cls._fallback_rate_limit(email, ip)

    @classmethod
    def _fallback_rate_limit(cls, email: str, ip: Optional[str]) -> Optional[str]:
        now = time.monotonic()
        ek = f"e:{email}"
        lst = cls._rate_store.setdefault(ek, [])
        lst[:] = [t for t in lst if now - t < cls.RATE_LIMIT_PER_EMAIL_WINDOW]
        lst.append(now)
        if len(lst) > cls.RATE_LIMIT_PER_EMAIL_MAX:
            return f"该邮箱发送过于频繁，请 {cls.RATE_LIMIT_PER_EMAIL_WINDOW} 秒后重试"
        if ip:
            ik = f"ip:{ip}"
            il = cls._rate_store.setdefault(ik, [])
            il[:] = [t for t in il if now - t < cls.RATE_LIMIT_PER_IP_WINDOW]
            il.append(now)
            if len(il) > cls.RATE_LIMIT_PER_IP_MAX:
                return f"发送过于频繁，请 {cls.RATE_LIMIT_PER_IP_WINDOW} 秒后重试"
        return None

    # ------------------------------------------------------------------ #
    # 发送
    # ------------------------------------------------------------------ #
    @classmethod
    async def send_verification_email(cls, email: str, code: str, code_type: str) -> bool:
        """
        发送验证码邮件

        Args:
            email: 邮箱地址
            code: 验证码
            code_type: 验证码类型

        Returns:
            是否发送成功
        """
        from base.common.setting import settings as _settings

        # 如果邮件服务未启用或未配置，则只在日志中输出
        if not _settings.EMAIL_ENABLED or not _settings.SENDER_EMAIL or not _settings.SENDER_PASSWORD:
            logger.warning(f"====== 验证码邮件（未配置SMTP，仅输出到日志）=======")
            logger.warning(f"收件人: {email}")
            logger.warning(f"类型: {code_type}")
            logger.warning(f"验证码: {code}")
            logger.warning(f"有效期: {cls.CODE_EXPIRE_MINUTES} 分钟")
            logger.warning(f"==================================================")
            await asyncio.sleep(0.1)
            return True

        try:
            # 根据类型设置邮件内容
            type_names = {
                "register": "注册",
                "login": "登录",
                "reset_password": "重置密码",
                "identity": "身份关联",
            }
            type_name = type_names.get(code_type, code_type)

            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"{_settings.SENDER_NAME} - {type_name}验证码"
            msg['From'] = formataddr((_settings.SENDER_NAME, _settings.SENDER_EMAIL))
            msg['To'] = email

            # 邮件正文（HTML格式）
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                    .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                    .code {{ background: white; border: 2px dashed #667eea; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; color: #667eea; letter-spacing: 5px; margin: 20px 0; border-radius: 5px; }}
                    .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; }}
                    .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>{_settings.SENDER_NAME}</h2>
                        <p>{type_name}验证码</p>
                    </div>
                    <div class="content">
                        <p>您好，</p>
                        <p>您正在进行{type_name}操作，您的验证码是：</p>
                        <div class="code">{code}</div>
                        <p><strong>验证码有效期为 {cls.CODE_EXPIRE_MINUTES} 分钟。</strong></p>
                        <p>如果这不是您的操作，请忽略此邮件。</p>
                        <div class="footer">
                            <p>此邮件由系统自动发送，请勿回复。</p>
                            <p>{_settings.SENDER_NAME} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """

            # 添加HTML内容
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)

            # 连接SMTP服务器并发送邮件
            if _settings.SMTP_USE_TLS:
                server = smtplib.SMTP(_settings.SMTP_HOST, _settings.SMTP_PORT)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(_settings.SMTP_HOST, _settings.SMTP_PORT)

            server.login(_settings.SENDER_EMAIL, _settings.SENDER_PASSWORD)
            server.sendmail(_settings.SENDER_EMAIL, [email], msg.as_string())
            server.quit()

            logger.info(f"验证码邮件已发送到 {email}")
            return True

        except Exception as e:
            logger.error(f"发送邮件失败: {str(e)}")
            # 发送失败时，在日志中输出验证码（便于开发调试）
            logger.warning(f"====== 验证码（邮件发送失败，仅输出到日志）=======")
            logger.warning(f"收件人: {email}")
            logger.warning(f"类型: {code_type}")
            logger.warning(f"验证码: {code}")
            logger.warning(f"有效期: {cls.CODE_EXPIRE_MINUTES} 分钟")
            logger.warning(f"==================================================")
            return False

    @classmethod
    async def send_code(cls, email: str, code_type: str) -> Tuple[bool, str]:
        """
        发送验证码（生成 → 存储 → 投递）

        Args:
            email: 邮箱地址
            code_type: 验证码类型 (register/login/reset_password/identity)

        Returns:
            (是否成功, 消息)
        """
        code = cls.generate_code()
        await cls.store_code(email, code, code_type)
        success = await cls.send_verification_email(email, code, code_type)
        if success:
            return True, f"验证码已发送到 {email}，{cls.CODE_EXPIRE_MINUTES}分钟内有效"
        return False, "验证码发送失败，请稍后重试"

    @classmethod
    def cleanup_expired_codes(cls):
        """清理过期验证码（进程内降级存储的定时清理；Redis 由 TTL 自动过期）。"""
        now = datetime.now()
        expired_keys = [
            key for key, expire_time in cls._code_expire_time.items()
            if now > expire_time
        ]
        for key in expired_keys:
            cls._verification_codes.pop(key, None)
            cls._code_expire_time.pop(key, None)
        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期验证码")
